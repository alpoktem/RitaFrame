import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify

from config_loader import ConfigLoader
from motionio import MotionController
from services import Services
from views import DEFAULT_VIEW, VIEWS, base_context, render_view

SECRET_KEY_ENV = 'FLASK_SECRET_KEY'


def setup_logging(debug):
    os.makedirs('logs', exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s',
                                  '%Y-%m-%d %H:%M:%S')

    file_handler = RotatingFileHandler('logs/app.log', maxBytes=1024 * 1024 * 5,
                                       backupCount=5)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    if debug:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)


def create_app(config_path='config.yaml', debug=None):
    if debug is None:
        debug = os.getenv('DEBUG_MODE', 'True') == 'True'
    setup_logging(debug)

    config = ConfigLoader(config_path)
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv(SECRET_KEY_ENV) or 'supersecretkey'

    services = Services(config)
    motion = MotionController(config)
    motion.start()

    app.extensions['config'] = config
    app.extensions['services'] = services
    app.extensions['motion'] = motion

    register_routes(app, config, services, motion)
    logging.info('RitaFrame starting: view=%s port=%s', config.get('view', DEFAULT_VIEW),
                 config.get('port', 8000))
    return app


def register_routes(app, config, services, motion):
    @app.route('/')
    def index():
        return render_view(config.get('view', DEFAULT_VIEW), config, services)

    @app.route('/view/<name>')
    def view_by_name(name):
        return render_view(name, config, services)

    @app.route('/api/clock')
    def api_clock():
        now = services.now()
        return jsonify({
            'time': now.strftime(config.get('clock_format', '%H:%M')),
            'date': now.strftime(config.get('date_format', '%A, %d %B')),
            'seconds': now.second,
        })

    @app.route('/api/weather')
    def api_weather():
        if not config.get('enable_weather', True):
            return jsonify({'enabled': False})
        return jsonify({'enabled': True, 'forecast': services.weather_forecast()})

    @app.route('/api/bus')
    def api_bus():
        if not config.get('enable_bus', True):
            return jsonify({'enabled': False})
        return jsonify({'enabled': True, 'bus': services.bus.get_departures()})

    @app.route('/api/photos/next')
    def api_photos_next():
        if not services.photos.enabled:
            return jsonify({'enabled': False, 'url': None})
        return jsonify({'enabled': True, 'url': services.photos.next_url(),
                        'status': services.photos.status})

    @app.route('/photos/auth')
    def photos_auth():
        """One-off Google OAuth login. Deliberately blocking: this is the setup step."""
        result = services.photos.authenticate()
        return jsonify(result), 200 if result.get('ok') else 400

    @app.route('/api/status')
    def api_status():
        """Diagnostics for a headless frame: active view, feature flags, service health."""
        bus_result = services.bus_departures() if config.get('enable_bus', True) else None
        return jsonify({
            'view': config.get('view', DEFAULT_VIEW),
            'available_views': sorted(VIEWS),
            'features': {
                'clock': bool(config.get('enable_clock', True)),
                'weather': bool(config.get('enable_weather', True)),
                'bus': bool(config.get('enable_bus', True)),
                'photos': services.photos.enabled,
                'photos_mode': services.photos.mode if services.photos.enabled else None,
                'motion_detection': motion.enabled,
            },
            'bus': {'ok': bus_result.get('ok'), 'error': bus_result.get('error')}
                   if bus_result else None,
            'photos': {'status': services.photos.status, 'error': services.photos.error,
                       'has_photo': services.photos.current_url() is not None},
            'render': base_context(config, services)['current_time'],
        })


app = create_app()


if __name__ == '__main__':
    config = app.extensions['config']
    app.run(host=config.get('host', '0.0.0.0'),
            port=int(os.getenv('PORT', config.get('port', 8000))),
            debug=os.getenv('DEBUG_MODE', 'True') == 'True')
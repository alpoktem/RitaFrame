"""View registry.

A view is a function ``view(config, services) -> str`` returning rendered HTML.
The active view is chosen by the ``view`` key in config.yaml; every registered
view is also reachable directly at ``/view/<name>`` so layouts can be compared
without editing config.
"""

from flask import render_template

DEFAULT_VIEW = 'clock'


def base_context(config, services, **extra):
    """Settings every view needs: colours, clock strings, optional photo backdrop."""
    now = services.now()
    context = {
        'current_time': now.strftime(config.get('clock_format', '%H:%M')),
        'current_date': now.strftime(config.get('date_format', '%A, %d %B')),
        'timezone': config.get('clock_timezone', 'Europe/Madrid'),
        'background_color': config.get('background_color', '#000000'),
        'text_color': config.get('text_color', '#ffffff'),
        'muted_text_color': config.get('muted_text_color', '#8a8a8a'),
        # None unless photos are enabled in background mode, so templates can skip it.
        'background_image': services.photos.background_url(),
        'overlay_opacity': config.get('photos_overlay_opacity', 0.45),
        'refresh_secs': config.get('bus_poll_interval_secs', 60),
    }
    context.update(extra)
    return context


def clock_view(config, services):
    """Clock, three-day forecast, and live bus departures."""
    return render_template('clock.html', **base_context(
        config, services,
        enable_clock=config.get('enable_clock', True),
        enable_weather=config.get('enable_weather', True),
        enable_bus=config.get('enable_bus', True),
        weather_location=config.get('weather_location', 'Barcelona,ES'),
        weather_forecast=services.weather_forecast() if config.get('enable_weather', True) else [],
        bus_stops=services.bus_departures() or [],
    ))


def photos_view(config, services):
    """Full-screen photo carousel."""
    return render_template('photos.html',
                           photo=services.photos.next_url() or '',
                           background_color=config.get('background_color', '#000000'),
                           transition_time_ms=config.get('transition_time_ms', 1000),
                           display_duration_ms=config.get('display_duration_ms', 10000))


VIEWS = {
    'clock': clock_view,
    'photos': photos_view,
}


def render_view(name, config, services):
    """Render a view by name, falling back to the default for unknown names."""
    view = VIEWS.get(name)
    if view is None:
        from flask import abort
        abort(404)
    return view(config, services)
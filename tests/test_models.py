from fractal_flight_studio.models import RenderMode, RenderRequest, Viewport


def test_zoom_keeps_selected_complex_point_stable():
    viewport = Viewport(-0.5, 0.0, 3.5)
    before = viewport.pixel_to_complex(700, 220, 1000, 600)
    zoomed = viewport.zoom_at(700, 220, 1000, 600, 2.0)
    after = zoomed.pixel_to_complex(700, 220, 1000, 600)
    assert after == before
    assert zoomed.width == 1.75


def test_request_validation():
    RenderRequest(width=10, height=10).validate()
    RenderRequest(width=10, height=10, render_mode=RenderMode.PERTURBATION, reference_bits=512).validate()

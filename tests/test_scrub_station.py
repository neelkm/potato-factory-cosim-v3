import pytest
from scrub_station import scrub_complete,brush_specs,MIN_CONTACT_SECONDS,MIN_SLIP_METRES

@pytest.mark.parametrize('seconds,slip,expected',[
    (0,0,False),(10,0,False),(0,10,False),
    (MIN_CONTACT_SECONDS-.001,MIN_SLIP_METRES+1,False),
    (MIN_CONTACT_SECONDS+1,MIN_SLIP_METRES-.001,False),
    (MIN_CONTACT_SECONDS,MIN_SLIP_METRES,True),
])
def test_cleaning_requires_both_contact_and_motion(seconds,slip,expected):
    assert scrub_complete(seconds,slip) is expected

def test_brush_envelopes_fit_singulation_guides():
    # The guides narrow toward the inspector. Brush collision envelopes must
    # remain inside that taper, with positive clearance for the mounted shafts.
    specs=brush_specs()
    for spec in specs:
        x=spec['pos'][0];guide_half_width=.80-(x-1.05)*.748/2.25
        assert 0<spec['width']/2<guide_half_width-.02
        assert spec['speed_ratio']<0  # Underside feeds in +X for a Y-axis rotor.
    assert all(b['pos'][0]-a['pos'][0]>a['radius']+b['radius'] for a,b in zip(specs,specs[1:]))

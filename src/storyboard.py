"""Select station moments from measured controller and ownership events."""
import json
from config import OUT
def storyboard(meta):
    events=meta['events'];full=[e for e in events if e['kind']=='box_full'];attach=[e for e in events if e['kind']=='vacuum_attached'];release=[e for e in events if e['kind']=='vacuum_released'];fork=next(e for e in events if e['kind']=='forklift_start')
    if len(full)!=6 or len(attach)!=6 or len(release)!=6 or not meta.get('forklift_complete') or meta.get('error'):raise RuntimeError('The complete co-simulation must pass before rendering its film')
    outcomes={o['potato']:o for o in meta['outcomes']};rejects=[e for e in events if e['kind']=='reject' and outcomes[e['potato']]['location']=='discard'];reject=rejects[min(2,len(rejects)-1)]
    first=full[0]['time'];grip=attach[0]['time'];last_release=release[-1]['time'];ft=fork['time'];wash=min(meta['wash_times'].values())+4
    def shot(view,duration,t0,rate,title,caption,move=(0,0,0),**kw):return dict(view=view,duration=duration,t0=t0,rate=rate,title=title,caption=caption,move=move,**kw)
    shots=[
        shot('Overall',4,wash,1,'FROM FIELD TO PALLET  /  3.0','NVIDIA cosim · Three coordinated simulation engines',(-.7,.5,-.15)),
        shot('Truck unloading',5,15.5,1,'01  GENTLE UNLOADING','PhysX contacts carry potatoes onto the receiving belt',(-.2,.3,.15)),
        shot('Water wash',6,wash,1,'02  ROLLER WASH','Twice the water flow · Physical spray and produce contacts',(-.25,.12,-.1)),
        shot('Quality & rejection',6,reject['time']-.7,.5,'03  CHECK & DIVERT','FMI inspection and pneumatic response · Half speed',(-.15,.1,.05),tracked=reject['potato'],event_time=reject['time']),
        shot('Carton filling',4,first-3.8,1,'04  FILL A LIGHTWEIGHT CARTON','Counted produce arrives on the output belt',(-.12,.1,.03)),
        shot('Carton closing',4,first+.2,1,'05  CLOSE THE CARTON','PhysX folds the lids before the ownership handoff',(.08,.1,.05)),
        shot('Robot palletizing',4,grip-.4,1,'06  SEAL & LIFT','Newton · Four suction contacts · Real motor limits',(-.06,.05,-.02),eye=(8.7,1.0,2.25),target=(7.95,0,1.43)),
        shot('Robot palletizing',6,grip+3,3,'CARRY TO THE PALLET','Dynamic carton and contents · Three-times speed',(-.2,.12,-.05)),
        shot('Robot palletizing',4,last_release-2,1,'SIX CARTONS, ONE PALLET','The final carton settles before the suction cups release',(-.1,.1,-.03)),
        shot('Forklift dispatch',3,ft+12,1,'07  LIFT THE LOAD','The completed pallet returns to PhysX',eye=(12.8,-3.1,3.6),target=(8.17,-2.3,1.3)),
        shot('Forklift dispatch',4,ft+16,5,'MOVE TO DISPATCH','SimReady forklift · Contact-supported load · Five-times speed'),
        shot('Forklift dispatch',4,ft+44,1,'SET DOWN & RELEASE','Six cartons arrive at the dispatch station',eye=(17,-10,4.3),target=(13,-6.3,.7)),
        shot('Factory hero',3,min(meta['seconds']-3,ft+52),1,'FIELD / FLOW  3.0','Blender · OpenUSD · NVIDIA cosim · RTX',(-1.,-.3,.3)),
    ]
    (OUT/'storyboard.json').write_text(json.dumps(shots,indent=2));return shots

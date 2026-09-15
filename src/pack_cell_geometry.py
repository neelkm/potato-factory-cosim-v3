"""Compact cartons, packing conveyor, pallet support and FR3 pedestal."""
# Executed by build_scene.py inside its Blender authoring namespace.
body('CartonBelt',(7.95,.86,1.07),12,[((0,0,0),(.38,2.12,.14))],beltmat,True)
manifest['belts'].append(dict(name='CartonBelt',velocity=(0,0,0)))
for xx in [7.80,8.10]:
    for yy in [-.10,1.79]:
        box('Carton_conveyor_leg',(xx,yy,.50),(.04,.04,1.0),steel)
        cyl('Carton_conveyor_foot',(xx,yy,.025),.045,.045,dark)
    box('Carton_conveyor_brace',(xx,.845,.30),(.026,1.91,.03),dark)
static('Carton_stop',(7.95,-.132,1.175),(.36,.02,.06),steel)
for xx in [7.78,8.12]:static('Carton_feed_guard',(xx,.87,1.175),(.012,2.05,.06),steel)
for i in range(6):
    loc=(7.95,i*.34,FILL[2]);lx,ly,h=BOX_SIZE
    shapes=[((0,0,.004),(lx,ly,.008)),((0,-ly/2,h/2),(lx,.006,h)),((0,ly/2,h/2),(lx,.006,h)),((-lx/2,0,h/2),(.006,ly,h)),((lx/2,0,h/2),(.006,ly,h))]
    root=body(f'Box_{i}',loc,.13,shapes,card)
    text('Carton_brand','FIELD / FLOW',(0,-ly/2-.004,.105),.026,green,parent=root)
    text('Carton_contents','FRESH BABY POTATOES',(0,-ly/2-.004,.057),.012,dark,parent=root)
    for j,(p,sz,axis,sign) in enumerate([((0,-ly/2,h),(lx,.004,ly/2),'X',1),((0,ly/2,h),(lx,.004,ly/2),'X',-1),((-lx/2,0,h),(.004,ly,lx/2),'Y',-1),((lx/2,0,h),(.004,ly,lx/2),'Y',1)]):
        if j<2:p=(p[0],p[1],p[2]+.010)
        length=sz[2]-.003;sz=(sz[0]-.012,sz[1],length) if j<2 else (sz[0],sz[1]-.012,length)
        hinge=tuple(loc[k]+p[k] for k in range(3));fname=f'Flap_{i}_{j}'
        body(fname,hinge,.008,[((0,0,length/2),sz)],card)
        manifest['flaps'].append(dict(name=fname,box=f'Box_{i}',anchor=p,axis=axis,target=-sign*90))
shapes=[]
for xx in [-.40,.40]:
    for yy in [-.24,.24]:shapes.append(((xx,yy,.0825),(.10,.09,.095)))
for xx in [-.42,-.21,0,.21,.42]:shapes.append(((xx,0,.1375),(.19,.63,.025)))
for xx in [-.40,0,.40]:shapes.append(((xx,0,.0175),(.11,.63,.035)))
body('Pallet',PALLET,7,shapes,wood)
static('Pallet_loading_table',(8.17,-1.02,.59),(1.12,.76,.06),steel)
for xx in [7.66,8.68]:
    for yy in [-1.32,-.72]:static('Pallet_table_leg',(xx,yy,.29),(.055,.055,.58),dark)
static('Robot_plinth',(8.15,-.50,.475),(.36,.36,.95),white)
text('Robot_label','FRANKA / PACK',(8.15,-.687,.50),.04,green)
# Native PhysX actuator roots. Detailed SimReady meshes are imported below.
for name,mass,shapes in [('Forklift',2700,[((0,0,.56),(1.15,2.08,.95))]),('Forks',65,[((-.293,1.887,.125),(.102,1.118,.040)),((.293,1.887,.125),(.102,1.118,.040)),((0,1.34,.69),(1.12,.065,1.04))])]:
    empty(name,(8.17,-7.5,0));manifest['bodies'].append(dict(name=name,pos=(8.17,-7.5,0),mass=mass,shapes=shapes,kinematic=True))
text('Shipping_sign','07 / DISPATCH',(13,-6.0,.012),.35,white,rot=(0,0,0))
for yy in [-7.2,-5.7]:box('Pallet_bay',(13,yy,.006),(2.1,.06,.008),yellow,bevel=0)

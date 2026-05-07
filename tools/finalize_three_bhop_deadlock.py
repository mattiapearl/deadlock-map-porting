#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, shutil, subprocess, time, hashlib, re
from pathlib import Path

ROOT=Path('C:/Code/deadlock-map-porting')
CSDK=Path('C:/Users/User/Documents/Reduced_CSDK_12')
GAME=CSDK/'game/citadel'
RI=CSDK/'game/bin_cs2/win64/resourceinfo.exe'
RC=CSDK/'game/bin_cs2/win64/resourcecompiler.exe'
LIVE=Path('C:/Program Files (x86)/Steam/steamapps/common/Deadlock/game/citadel/addons/pak72_dir.vpk')

spec=importlib.util.spec_from_file_location('bhop_colour_builder', ROOT/'tools/build_bhop_colour_preserve_port.py')
bc=importlib.util.module_from_spec(spec); spec.loader.exec_module(bc)

MAPS={
 'bhop_soulscape': Path('C:/Code/deadlock-map-porting/new_workshop_maps/3605179998/nested_extract'),
 'bhop_quit_full': Path('C:/Code/deadlock-map-porting/new_workshop_maps/3647098259/nested_extract'),
 'bhop_rose': Path('C:/Code/deadlock-map-porting/new_workshop_maps/3660240969/nested_extract'),
}
PREFABS={'team_select','terrorist_team_intro','counterterrorist_team_intro','end_of_match'}

def run(cmd, **kw):
    print('$',' '.join(map(str,cmd)))
    cp=subprocess.run([str(c) for c in cmd],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,**kw)
    if cp.returncode:
        print(cp.stdout[-4000:]); raise SystemExit(cp.returncode)
    return cp.stdout

def entity_values(mapname, nested_root):
    ents=nested_root/'maps'/mapname/'entities/default_ents.vents_c'
    txt=run([RI,'-game',GAME,'-i',ents,'-all'])
    vals=[bc.parse_values_block(b) for b in bc.iter_values_blocks(txt)]
    return [v for v in vals if 'classname' in v]

def bounds_from_entities(vals):
    pts=[]
    for v in vals:
        if 'origin' in v:
            pts.append(bc.parse_vec3(v.get('origin')))
    if not pts: return (-16000,-16000,-4096),(16000,16000,4096),(0,0,128)
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]; zs=[p[2] for p in pts]
    mins=(min(xs)-2048,min(ys)-2048,min(zs)-2048); maxs=(max(xs)+2048,max(ys)+2048,max(zs)+4096)
    # prefer first CS2 player spawn as course spawn anchor
    sp=next((bc.parse_vec3(v.get('origin')) for v in vals if v.get('classname','').startswith('info_player_')), ((mins[0]+maxs[0])/2,(mins[1]+maxs[1])/2,max(zs)+128))
    return mins,maxs,sp

def make_patch(mapname,nested_root,work):
    vals=entity_values(mapname,nested_root)
    worldspawn=next((v for v in vals if v.get('classname')=='worldspawn'), {'classname':'worldspawn','worldname':mapname})
    mins,maxs,spawn=bounds_from_entities(vals)
    entities=[]; node_id=1000; kept=skipped=converted_spawns=0
    for v in vals:
        cls=v.get('classname','')
        if cls=='worldspawn' or cls in PREFABS:
            skipped+=1; continue
        made=bc.make_entity_from_values(v,node_id)
        if made:
            eid,block,node_id=made; entities.append((eid,block)); kept+=1
            if cls.startswith('info_player_'): converted_spawns+=1
    # Deadlock-native lights from CS2 lights, conservative and capped for stability.
    light_i=0
    for v in vals:
        if v.get('classname')!='light_omni2': continue
        x,y,z=bc.parse_vec3(v.get('origin'))
        color=v.get('color','255 245 220')
        rng=bc.parse_vec3(v.get('range'),(650,0,0))[0]
        try: bright=float(v.get('brightness','1'))
        except Exception: bright=1.0
        light_rgb = color if len(color.split()) == 3 else '255 245 220'
        light_range = max(384, min(2400, rng * 1.45))
        light_brightness = max(0.25, min(6.0, bright * 0.85))
        eid,block=bc.amp.make_cmap_entity(
            classname='citadel_volume_omni', origin=(x,y,z), node_id=node_id,
            targetname=f'{mapname}_dl_omni_{light_i:03d}', angles=(90,0,0),
            extra_props={
                'useLocalOffset':'0', 'enabled':'1', 'clientsideentity':'1',
                'directlight':'1', 'bouncelight':'1', 'bouncescale':'1',
                'colormode':'0', 'color': light_rgb, 'lightcolor': light_rgb,
                'brightness': f'{light_brightness:.3f}', 'brightness_legacy': f'{light_brightness:.3f}',
                'brightness_units':'1', 'brightness_lumens':'2500', 'brightness_candelas':'199', 'brightness_nits':'24539',
                'range': f'{light_range:.3f}', 'lightrange': f'{light_range:.3f}', 'lightbrightness': f'{light_brightness:.3f}',
                'shape':'3', 'skirt':'0', 'style':'0', 'attenuation1':'0', 'attenuation2':'1', 'lightsourceradius':'2',
                'mediacolor':'0 0 0 0','mediabrightness':'0','mediadensity':'0','animated':'0',
                'startlightbrightness': f'{light_brightness:.3f}', 'endlightbrightness':'0', 'startlightradius':'0', 'endlightradius': f'{light_range:.3f}',
                'startmediabrightness':'0', 'endmediabrightness':'0', 'startmediadensity':'0', 'endmediadensity':'0',
            })
        node_id+=1; light_i+=1; entities.append((eid,block))
    # Broad ambience helpers: final safety net so maps are never black.
    cx=(mins[0]+maxs[0])/2; cy=(mins[1]+maxs[1])/2; cz=(mins[2]+maxs[2])/2
    for i,(ox,oy) in enumerate([(0,0),(-0.25,-0.25),(0.25,0.25),(-0.25,0.25),(0.25,-0.25)]):
        broad_range=str(max(3000,min(11000,max(maxs[0]-mins[0],maxs[1]-mins[1])*0.75)))
        eid,block=bc.amp.make_cmap_entity(classname='citadel_volume_omni', origin=(cx+(maxs[0]-mins[0])*ox, cy+(maxs[1]-mins[1])*oy, cz+800), node_id=node_id, targetname=f'{mapname}_broad_light_{i}', angles=(90,0,0), extra_props={
            'useLocalOffset':'0','enabled':'1','clientsideentity':'1','directlight':'1','bouncelight':'1','bouncescale':'1',
            'colormode':'0','color':'255 245 220','lightcolor':'255 245 220','brightness':'8','brightness_legacy':'8','brightness_units':'1',
            'brightness_lumens':'6000','brightness_candelas':'500','brightness_nits':'60000','range':broad_range,
            'lightbrightness':'8','lightrange':broad_range,'shape':'3','skirt':'0','style':'0','attenuation1':'0','attenuation2':'1','lightsourceradius':'2',
            'mediacolor':'0 0 0 0','mediabrightness':'0','mediadensity':'0','animated':'0',
            'startlightbrightness':'8','endlightbrightness':'0','startlightradius':'0','endlightradius':broad_range,
            'startmediabrightness':'0','endmediabrightness':'0','startmediadensity':'0','endmediadensity':'0'})
        node_id+=1; entities.append((eid,block))
    # Team spawns and required Deadlock target anchors at actual CS2 start.
    sx,sy,sz=spawn; sz+=64
    for team,yoff,yaw in [(2,64,180),(3,-64,0)]:
        for i in range(8):
            eid,block=bc.amp.make_cmap_entity(classname='info_team_spawn', origin=(sx+(i%4-1.5)*64, sy+yoff+(i//4)*64, sz), node_id=node_id, teamnumber=team, lane_num=0, initial_spawn=False, angles=(0,yaw,0))
            node_id+=1; entities.append((eid,block))
    for tn,off in [('bhop_course_start',0),('rebels_vanguard_spawn',64),('combine_vanguard_spawn',-64)]:
        eid,block=bc.amp.make_cmap_entity(classname='info_target_server_only', origin=(sx,sy+off,sz), node_id=node_id, targetname=tn, extra_props={'useLocalOffset':'0'})
        node_id+=1; entities.append((eid,block))
    for origin in [mins,maxs]:
        eid,block=bc.amp.make_cmap_entity(classname='citadel_minimap_boundary', origin=origin, node_id=node_id); node_id+=1; entities.append((eid,block))
    eid,block,node_id=bc.amp.make_solid_box_entity_from_template(classname='citadel_trigger_suspend_modifier', mins=mins, maxs=maxs, node_id_start=node_id, targetname=f'{mapname}_roam_hideout_volume', modifier_name='modifier_citadel_in_hideout_zone')
    entities.append((eid,block))
    vmap=CSDK/'content/citadel_addons'/f'{mapname}_entity_final'/'maps'/f'{mapname}.vmap'
    if vmap.parent.parent.exists(): shutil.rmtree(vmap.parent.parent)
    bc.insert_entities_into_empty_vmap(vmap, entities, worldspawn)
    patch_vpk=bc.compile_entity_patch_vpk(vmap)
    patch_extract=work/f'{mapname}_patch_extract'; patch_extract.mkdir()
    run(['vpk','-x',patch_extract,patch_vpk])
    patched=patch_extract/'maps'/mapname/'entities/default_ents.vents_c'
    print(mapname,'kept',kept,'skipped',skipped,'spawns',converted_spawns,'dl_lights',light_i,'anchor',spawn)
    return patched

def main():
    stamp=time.strftime('%Y%m%d_%H%M%S')
    work=ROOT/'work'/f'finalize_three_bhop_{stamp}'; work.mkdir(parents=True)
    backup=ROOT/'live_backups'/f'finalize_three_bhop_{stamp}'; backup.mkdir(parents=True)
    if LIVE.exists(): shutil.copy2(LIVE, backup/LIVE.name)
    live_extract=work/'live_extract'; live_extract.mkdir()
    run(['vpk','-x',live_extract,LIVE])
    # remove unsafe prefab VPK hacks; entity patches remove prefab entities instead.
    prefdir=live_extract/'maps/prefabs/misc'
    if prefdir.exists(): shutil.rmtree(prefdir)
    for mapname,nested_root in MAPS.items():
        patched_ents=make_patch(mapname,nested_root,work)
        nested=work/f'{mapname}_nested'; shutil.copytree(nested_root,nested)
        # Copy the entire compiled entity output, not only default_ents.vents_c.
        # Solid helper entities reference generated VMDLs from maps/<map>/entities/.
        patch_entities_dir=patched_ents.parent
        dst_entities_dir=nested/'maps'/mapname/'entities'
        shutil.copytree(patch_entities_dir, dst_entities_dir, dirs_exist_ok=True)
        new_nested=work/f'{mapname}.vpk'; run(['vpk','-c',nested,new_nested])
        shutil.copy2(new_nested, live_extract/'maps'/f'{mapname}.vpk')
    newpak=work/'pak72_dir.vpk'; run(['vpk','-c',live_extract,newpak])
    shutil.copy2(newpak,LIVE)
    print('backup',backup)
    print('installed',LIVE,LIVE.stat().st_size,hashlib.sha256(LIVE.read_bytes()).hexdigest())

if __name__=='__main__': main()

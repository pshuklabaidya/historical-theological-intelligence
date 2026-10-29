"""Stdlib package/ownership/registry validator, used by the assembled Skill."""
from pathlib import Path
import ast,json,hashlib,re

def validate(root):
 errors=[]
 def need(ok,msg):
  if not ok:errors.append(msg)
 sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 try:
  files={str(p.relative_to(root)):p for p in root.rglob('*') if p.is_file()}
  need(not any(p.is_symlink() for p in root.rglob('*')),'symlink in production')
  manifest={p:h for h,p in (l.split('  ',1) for l in (root/'SHA256SUMS.txt').read_text().splitlines())}
  need(set(manifest)==set(files)-{'SHA256SUMS.txt'},'manifest exact path set')
  for p,h in manifest.items():need(p in files and sha(files[p])==h,'manifest hash: '+p)
  r=json.loads((root/'registry/capabilities.json').read_text());lock=json.loads((root/'registry/lock.json').read_text());owners=json.loads((root/'registry/ownership.json').read_text())
  need(set(owners['files'])==set(files),'ownership exact path set')
  need(len(r['operations'])==38,'exact 38 operations')
  routing=ast.parse((root/'scripts/hti_core/natural_language_routing.py').read_text());enum=next(n for n in routing.body if isinstance(n,ast.ClassDef) and n.name=='OperationID');ops={n.value.value for n in enum.body if isinstance(n,ast.Assign)};need(set(r['operations'])==ops,'OperationID equality')
  need(len(r['modules'])==9 and all(v['may_publish']==(m=='kernel') for m,v in r['modules'].items()),'single kernel publisher')
  for path,h in lock['files'].items():need(sha(root/'registry'/path)==h,'registry lock: '+path)
  need(lock['candidate_version']==r['candidate_version']==owners['candidate_version'],'candidate version equality')
  need(('version: '+r['candidate_version']) in (root/'SKILL.md').read_text(),'Skill candidate version')
  seen=set();visiting=set()
  def visit(op):
   if op in seen:return
   need(op not in visiting,'dependency cycle: '+op)
   if op in visiting:return
   visiting.add(op)
   for d in r['operations'][op]['requires_operations']:
    need(d in r['operations'],'unknown dependency: '+d)
    if d in r['operations']:visit(d)
   visiting.remove(op);seen.add(op)
  producers=set()
  for key,obj in r['state_objects'].items():
   slot=(obj['path'],obj.get('logical_object'));need(slot not in producers,'duplicate state producer: '+key);producers.add(slot);need(obj['producer_module'] in r['modules'],'unknown producer: '+key)
  for op,v in r['operations'].items():
   visit(op);need(v['owner'] in r['modules'],'unknown owner: '+op)
   need(set(v['requires_state']+v['produces_state'])<=set(r['state_objects']),'unknown state: '+op)
   for path in v['instructions']:need(path in files,'missing operation instruction: '+path)
   for entry in [v['validator'],v['additional_validator']]:
    if not entry:continue
    mod,fn=entry.split(':');p=root/'scripts'/(mod.replace('.','/')+'.py');need(p.is_file(),'missing validator module: '+entry)
    if p.is_file():need(any(isinstance(n,ast.FunctionDef) and n.name==fn for n in ast.parse(p.read_text()).body),'missing validator entry: '+entry)
  for m,info in r['modules'].items():
   contract=json.loads((root/info['contract']).read_text());need(contract['module_id']==m and contract['module_version'] if False else contract['module_id']==m,'contract owner')
   need(contract['version']==info['version'] and contract['operations']=={op:r['operations'][op] for op in info['operations']},'contract projection: '+m)
   for p in info['instructions']:need(p in files,'missing module instruction: '+p)
  for p,owner in owners['files'].items():
   need(owner in r['modules'],'unknown file owner: '+p)
   need(not any(x in p.split('/') for x in ['dev','tests','fixtures','__pycache__','evaluator']),'development artifact: '+p)
   if p.endswith('.py'):
    tree=ast.parse(files[p].read_text())
    if owner!='kernel':
     for n in ast.walk(tree):
      if isinstance(n,ast.ImportFrom) and n.module=='terminal_output':need(all(a.name!='publish' for a in n.names),'nonkernel publisher import: '+p)
      if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='terminal_output':need(n.func.attr!='publish','nonkernel publish: '+p)
  need(sum(p.endswith('/SKILL.md') or p=='SKILL.md' for p in files)==1,'one Skill entry')
 except (OSError,ValueError,KeyError,TypeError,StopIteration,SyntaxError) as e:errors.append(type(e).__name__+': '+str(e))
 return errors

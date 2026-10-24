"""Audited pure decoder subset; provenance: profiles/98348-braxis.json.
No backend import, sys.path mutation, image loader or process entrypoint.
"""
import struct

MASK=0xffffffff
def rot(x,n):return ((x<<n)|(x>>(32-n)))&MASK
def hash_name(data,seed=0x18273645):
 a=b=c=(seed+len(data))&MASK
 p=0;n=len(data)
 while n>12:
  x,y,z=struct.unpack_from('<III',data,p);a=(a+x)&MASK;b=(b+y)&MASK;c=(c+z)&MASK
  a=((a-c)^rot(c,4))&MASK;c=(c+b)&MASK
  b=((b-a)^rot(a,6))&MASK;a=(a+c)&MASK
  c=((c-b)^rot(b,8))&MASK;b=(b+a)&MASK
  a=((a-c)^rot(c,16))&MASK;c=(c+b)&MASK
  b=((b-a)^rot(a,19))&MASK;a=(a+c)&MASK
  c=((c-b)^rot(b,4))&MASK;b=(b+a)&MASK
  p+=12;n-=12
 if n==0:return c
 tail=data[p:];a=(a+int.from_bytes(tail[:4],'little'))&MASK;b=(b+int.from_bytes(tail[4:8],'little'))&MASK;c=(c+int.from_bytes(tail[8:12],'little'))&MASK
 c=((c^b)-rot(b,14))&MASK;a=((a^c)-rot(c,11))&MASK;b=((b^a)-rot(a,25))&MASK
 c=((c^b)-rot(b,16))&MASK;a=((a^c)-rot(c,4))&MASK;b=((b^a)-rot(a,14))&MASK;c=((c^b)-rot(b,24))&MASK
 return c

GLOBAL='libSCHO_gv_mMHO_HiveControlBeacons'
AGG='libSCHO_gs_MMHO_HiveControlBeacons'
SIG=('<'+AGG).encode()
class Refused(ValueError):pass
def descriptor(t,p,depth=0,seen=None):
 if depth>4:raise Refused('type_depth')
 seen=set() if seen is None else seen
 if p in seen:raise Refused('type_cycle')
 seen=seen|{p};r=t.read(p,80);sp,n=struct.unpack_from('<QI',r)
 if not 0<n<=512:raise Refused('signature_size')
 sig=t.read(sp,n+1)
 if sig[-1]!=0:raise Refused('signature_termination')
 result={'address':p,'signature':sig[:-1].decode('ascii'),'extent':struct.unpack_from('<I',r,0x40)[0],'aux':struct.unpack_from('<I',r,0x44)[0],'record_hex':r.hex()}
 if sig[:1] in [b'[',b'#']:
  child=struct.unpack_from('<Q',r,0x20)[0]
  if child:result['element']=descriptor(t,child,depth+1,seen)
 if sig[:-1]==SIG:
  member=struct.unpack_from('<Q',r,0x38)[0];visited=set();members=[]
  while member:
   if len(visited)>=16 or member in visited:raise Refused('member_cycle_or_bound')
   visited.add(member);mr=t.read(member,40);np,n=struct.unpack_from('<QI',mr)
   if not 0<n<=96:raise Refused('member_name_size')
   name=t.read(np,n+1)
   if name[-1]!=0:raise Refused('member_name_termination')
   members.append({'address':member,'name':name[:-1].decode('ascii'),'offset':struct.unpack_from('<I',mr,0x18)[0],'type':descriptor(t,struct.unpack_from('<Q',mr,0x10)[0],depth+1,seen),'record_hex':mr.hex()})
   member=struct.unpack_from('<Q',mr,0x20)[0]
  result['members']=members
 if t.read(p,80)!=r:raise Refused('type_changed')
 return result
def named_type(t):
 bucket=hash_name(SIG)&255;head=t.u(t.base+0x412c8a0+bucket*8);p=head;seen=set()
 while p:
  if p in seen or len(seen)>=128:raise Refused('type_bucket_bound')
  seen.add(p);r=t.read(p,80);sp,n=struct.unpack_from('<QI',r)
  if n==len(SIG) and t.read(sp,n+1)==SIG+b'\0':
   d=descriptor(t,p)
   if t.u(t.base+0x412c8a0+bucket*8)!=head:raise Refused('type_bucket_changed')
   return d
  p=struct.unpack_from('<Q',r,0x48)[0]
 raise Refused('named_type_absent')
def compiler_global(t):
 root=t.u(t.base+0x3b8c918)
 if not root:raise Refused('compiler_root_null')
 r=t.read(root,0x40);table=struct.unpack_from('<Q',r,8)[0]
 if not table:raise Refused('global_table_absent')
 target=GLOBAL.encode();head=t.u(table+8*(hash_name(target)&2047));p=head;seen=set()
 low=t.u(t.base+0x32c23c8,'I');high=t.u(t.base+0x32c209c,'I')
 while p:
  if p in seen or len(seen)>=128:raise Refused('symbol_bucket_bound')
  seen.add(p);s=t.read(p,64)
  if struct.unpack_from('<I',s,8)[0]==len(target):
   l,h=struct.unpack_from('<II',s);np=((h^high^0xe6f631ce)<<32)|(~(l-low)&0xffffffff)
   if t.read(np,len(target)+1)==target+b'\0':
    result={'name':GLOBAL,'address':p,'compiler_root':root,'kind':struct.unpack_from('<I',s,0x18)[0],'global_offset':struct.unpack_from('<I',s,0x1c)[0],'root_extent_at_capture':struct.unpack_from('<I',r,0x18)[0],'symbol_hex':s.hex(),'type':descriptor(t,struct.unpack_from('<Q',s,0x10)[0])}
    if result['kind']!=0x108:raise Refused('not_global_kind108')
    if t.u(t.base+0x3b8c918)!=root or t.read(p,64)!=s:raise Refused('compiler_changed')
    return result
  p=struct.unpack_from('<Q',s,0x38)[0]
 raise Refused('named_global_not_yet_published')

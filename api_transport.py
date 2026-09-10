"""RouterOS post-v6.43 binary API protocol, no third-party dependencies."""
import socket
import time
from urllib.parse import unquote

MAX_REPLY=4*1024*1024
class APIError(Exception):pass

def encode_length(n):
    if not 0<=n<=0xffffffff:raise APIError('Invalid API word size.')
    if n<0x80:return bytes([n])
    if n<0x4000:return (n|0x8000).to_bytes(2,'big')
    if n<0x200000:return (n|0xc00000).to_bytes(3,'big')
    if n<0x10000000:return (n|0xe0000000).to_bytes(4,'big')
    return b'\xf0'+n.to_bytes(4,'big')

def exact(sock,n):
    out=bytearray()
    while len(out)<n:
        chunk=sock.recv(n-len(out))
        if not chunk:raise APIError('Router closed the API connection.')
        out.extend(chunk)
    return bytes(out)

def read_length(sock):
    b=exact(sock,1)[0]
    if b<0x80:return b
    if b<0xc0:return ((b&0x3f)<<8)|int.from_bytes(exact(sock,1),'big')
    if b<0xe0:return ((b&0x1f)<<16)|int.from_bytes(exact(sock,2),'big')
    if b<0xf0:return ((b&0x0f)<<24)|int.from_bytes(exact(sock,3),'big')
    if b==0xf0:return int.from_bytes(exact(sock,4),'big')
    raise APIError('Unsupported API control byte.')

def sentence(sock,words):
    payload=bytearray()
    for word in words:
        encoded=str(word).encode('utf-8')
        if len(encoded)>MAX_REPLY:raise APIError('API request too large.')
        payload.extend(encode_length(len(encoded)));payload.extend(encoded)
    sock.sendall(payload+b'\0')

def response(sock):
    rows=[];used=0;error=False;deadline=time.monotonic()+20
    while True:
        if time.monotonic()>deadline:raise APIError('API response deadline exceeded.')
        words=[]
        while True:
            size=read_length(sock);used+=size+1
            if size>MAX_REPLY or used>MAX_REPLY:raise APIError('API response too large.')
            if size==0:break
            words.append(exact(sock,size).decode('utf-8'))
        if not words:continue
        kind=words[0]
        attributes={}
        for word in words[1:]:
            if word.startswith('=') and '=' in word[1:]:
                key,value=word[1:].split('=',1);attributes[key]=value
        if kind=='!re':rows.append(attributes)
        elif kind=='!trap':error=True
        elif kind=='!fatal':raise APIError('Router terminated the API request.')
        elif kind=='!empty':continue
        elif kind=='!done':
            if error:raise APIError('Router rejected the API request. Check permissions and supported commands.')
            return rows,attributes
        else:raise APIError('Unexpected API reply.')

def command(router,words):
    sock=socket.create_connection((router.host,router.port),timeout=15)
    try:
        if router.transport=='api-ssl':
            sock=router.tls_context().wrap_socket(sock,server_hostname=router.host)
            router.verify_peer(sock.getpeercert(binary_form=True))
        sentence(sock,['/login','=name='+router.username,'=password='+router.password])
        response(sock)
        sentence(sock,words)
        return response(sock)
    finally:sock.close()

def call(router,path,method,data=None):
    parts=unquote(path).strip('/').split('/')
    ident=parts.pop() if parts[-1].startswith('*') else None
    menu='/'+ '/'.join(parts)
    attrs=[]
    for k,v in (data or {}).items():
        if k=='.query':
            if not isinstance(v,list):raise APIError('Invalid query.')
            attrs.extend('?'+str(x) for x in v)
        else:
            if isinstance(v,list):v=','.join(map(str,v))
            if isinstance(v,bool):v='yes' if v else 'no'
            attrs.append('='+k+'='+str(v))
    if method=='GET':
        words=[menu+'/print']
        if menu=='/file':words+=['=.proplist=.id,name,type,size']
        if ident:words+=['?.id='+ident]
        rows,_=command(router,words)
        if ident:
            if len(rows)!=1:raise APIError('Router resource no longer exists.')
            return rows[0]
        if menu in ('/ipv6/settings','/system/device-mode','/system/clock','/system/ntp/client'):
            if len(rows)!=1:raise APIError('Expected one router settings record.')
            return rows[0]
        return rows
    if method=='PUT':
        rows,done=command(router,[menu+'/add']+attrs)
        uid=done.get('ret') or (rows[0].get('.id') if rows else None)
        if not uid:raise APIError('Create response did not return an ID; inspect the router before retrying.')
        return {**(data or {}),'.id':uid}
    if method in ('PATCH','DELETE'):
        if not ident:raise APIError('An explicit resource ID is required.')
        command(router,[menu+('/set' if method=='PATCH' else '/remove'),'=.id='+ident]+attrs)
        return {'.id':ident,**(data or {})} if method=='PATCH' else {}
    if method=='POST':
        rows,done=command(router,[menu]+attrs)
        return rows if rows else done
    raise APIError('Unsupported operation.')

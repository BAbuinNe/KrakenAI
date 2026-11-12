"""Private E5 inference endpoint for the Kraken AI web server."""
import hashlib, hmac, json, os, pathlib, tempfile, threading, urllib.request
from http.server import BaseHTTPRequestHandler
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('MKL_NUM_THREADS','1')
_ROOT=pathlib.Path('/tmp/kraken-e5')
_LOCK=threading.Lock()
_MODEL=None
_BASE='https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/onnx/'
_HASH='dd476dd0c2514e9b9be83aeb3853fac0763e0bdf4a71645407587d77c48a2d88'

def fetch(name, digest=None):
    _ROOT.mkdir(exist_ok=True)
    path=_ROOT/name
    if path.exists():return str(path)
    with tempfile.NamedTemporaryFile(dir=_ROOT,delete=False) as f:
        tmp=pathlib.Path(f.name)
        try:
            request=urllib.request.Request(_BASE+name,headers={'User-Agent':'KrakenAI-E5/1'})
            with urllib.request.urlopen(request,timeout=90) as source:
                sha=hashlib.sha256();total=0
                while True:
                    block=source.read(1024*1024)
                    if not block:break
                    total+=len(block)
                    if total>160*1024*1024:raise ValueError('Model too large')
                    sha.update(block);f.write(block)
            f.flush()
            if digest and sha.hexdigest()!=digest:raise ValueError('Model integrity check failed')
            tmp.replace(path)
        finally:
            if tmp.exists():tmp.unlink()
    return str(path)

def encode(texts):
    global _MODEL
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer
    with _LOCK:
        if _MODEL is None:
            tok=Tokenizer.from_file(fetch('tokenizer.json'))
            tok.enable_truncation(max_length=384)
            opts=ort.SessionOptions();opts.intra_op_num_threads=1;opts.inter_op_num_threads=1
            opts.enable_mem_pattern=False;opts.enable_cpu_mem_arena=False
            sess=ort.InferenceSession(fetch('model_qint8_avx512_vnni.onnx',_HASH),sess_options=opts,providers=['CPUExecutionProvider'])
            _MODEL=tok,sess
        tok,sess=_MODEL
        names={n.name for n in sess.get_inputs()}
        vectors=[]
        for i in range(0,len(texts),2):
            enc=tok.encode_batch(texts[i:i+2]);m=max(len(x.ids) for x in enc)
            ids=np.asarray([x.ids+[0]*(m-len(x.ids)) for x in enc],dtype=np.int64)
            mask=np.asarray([x.attention_mask+[0]*(m-len(x.attention_mask)) for x in enc],dtype=np.int64)
            feeds={'input_ids':ids,'attention_mask':mask,'token_type_ids':np.zeros_like(ids)}
            output=sess.run(None,{k:v for k,v in feeds.items() if k in names})[0]
            expanded=mask[:,:,None].astype(np.float32)
            p=(output*expanded).sum(axis=1)/np.maximum(expanded.sum(axis=1),1e-9)
            p/=np.maximum(np.linalg.norm(p,axis=1,keepdims=True),1e-9)
            vectors.extend(p.tolist())
        if any(len(v)!=384 for v in vectors):raise ValueError('Embedding dimension mismatch')
        return vectors

class handler(BaseHTTPRequestHandler):
    def reply(self,status,data):
        raw=json.dumps(data,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json')
        self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        self.reply(200,{'status':'ok','model':'multilingual-e5-small'})
    def do_POST(self):
        token=os.getenv('E5_SERVICE_TOKEN','')
        if not token or not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):
            return self.reply(401,{'error':'Unauthorized'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=100000:return self.reply(413,{'error':'Invalid size'})
            texts=json.loads(self.rfile.read(size))['texts']
            if not isinstance(texts,list) or not 1<=len(texts)<=32 or any(not isinstance(t,str) or not 1<=len(t)<=1500 for t in texts):
                return self.reply(422,{'error':'Invalid texts'})
            vectors=encode(texts)
            self.reply(200,{'vectors':vectors})
        except (ValueError,KeyError,TypeError):
            self.reply(422,{'error':'Invalid embedding request'})
        except Exception:
            self.reply(503,{'error':'E5 inference temporarily unavailable'})

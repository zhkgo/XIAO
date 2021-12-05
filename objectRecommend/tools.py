import numpy as np
import torch
from torchreid.utils import FeatureExtractor
from torchreid import metrics
from datatable import VideoDeepLink

extractor = FeatureExtractor(
    model_name='osnet_ain_x1_0',
    model_path='/data/zhkgo/datasets/osnet_ain_ms_d_c.pth.tar',
    device='cuda'
)
fps=30
basepath="/data/zhkgo/datasets/exp10/crops/person/"
paths=torch.load("paths.list")
g_features=torch.load("features.tensor")
g_camids=np.array([int(path.split('/')[-1].split('-')[0][5:]) for path in paths])
f_ids=np.array([int(path.split('/')[-1].split('-')[1]) for path in paths])



#layers index can make it faster
def matchBlock(vid,fid):
    global basepath
    pathBegin=basepath+'video'+str(vid)+'-'
    minDis=99999999
    pathReturn=[]
    for path in paths:
        if path.startswith(pathBegin):
            pid=int(path.split('/')[-1].split('-')[1])
            if abs(pid-fid)<minDis:
                minDis= abs(pid-fid)
                pathReturn=[path]
            elif abs(pid-fid)==minDis:
                pathReturn.append(path)
    return pathReturn
#video path /xxx/xx/xxx/videoxxx.mp4
def linkToCameraAndFrame(link):
    global fps
    vid=int(link.path.split('/')[-1].split('.')[0][5:])
    fid=int(link.timePoint*fps)
    return vid,fid
    

def count_near(ls,dis=150):
    beg=[ls[0]]
    cnt=[1]
    for i in range(1,len(ls)):
        if beg[-1]+dis>=ls[i]:
            cnt[-1]+=1
        else:
            cnt.append(1)
            beg.append(ls[i])
    return beg[np.argmax(cnt)]
    
def recommend(distmat,g_camids,f_ids,bound=4):
    '''
        distmat (numpy.ndarray): distance matrix of shape (num_query, num_gallery).
        g_camids (numpy.ndarray): shape(num_gallery)
        f_ids (numpy.ndarray): shape(num_gallery)
    '''
    d=np.argsort(distmat,axis=1)
    cids=[]
    for i in range(bound):
        cids.extend(g_camids[d[:,i]].tolist())
    mcid=np.argmax(np.bincount(cids))
    d=distmat[:,g_camids==mcid]
    f_ids=f_ids[g_camids==mcid]
    d=np.argsort(d,axis=1)
    fids=[]
    for i in range(bound):
        fids.extend(f_ids[d[:,i]].tolist())
    fids.sort()
    return mcid,count_near(fids)
def toDeepLink(vid,fid):
    global fps
    return VideoDeepLink(-1,"video"+str(vid)+".mp4",fid/fps)
    
def getMoreLink(linksIn):
    global g_features,paths,g_camids,g_fids
    matches=[]
    flt = (g_camids!=-1)
    for link in linksIn:
        vid,fid=linkToCameraAndFrame(link)
        matches.extend(matchBlock(vid,fid))
        flt = (flt & (g_camids!=vid))
    features=extractor(matches)
    l_features = g_features[flt]
    l_camids = g_camids[flt]
    l_fids = g_fids[flt]
    distmat = metrics.distance.cosine_distance(features, l_features)
    vid,fid=recommend(distmat,l_camids,l_fids)
    return [toDeepLink(vid,fid)]
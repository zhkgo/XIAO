"""
Created on Mon Jun 28 15:08:02 2021

@author: zhkgo
"""

from experiment import Experiment
from api.reid import ReIDTCP
import configparser
from bcifilter import BciFilter
from datatable import VideoDeepLink,Linker
from flask import Flask,request,render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from threading import Lock
from myresponse import success,fail
import importlib
import traceback
thread_lock = Lock()
_thread=None
_eegthread=None
conf = configparser.ConfigParser()
experiment=None
reID=None
linker=Linker()
app = Flask(__name__,static_url_path="")
app.config['JSON_AS_ASCII'] = False
app.config['SECRET_KEY'] = 'secret!'
CORS(app, supports_credentials=True)
socketio = SocketIO(app,cors_allowed_origins='*')



@app.route('/')
def page1():
    return render_template("video.html")
@app.route('/admin')
def pageAdmin():
    return render_template("admin.html", async_mode=socketio.async_mode)

#link 收发区
@socketio.on('pushlink',namespace='/pushDeeplink')
def recevDeepLink(jsondata):
    model=VideoDeepLink()
    for (key,value) in jsondata.items():
        model.__setattr__(key,value)
    linker.append(model)

def background_task():
    global linker,experiment
    experiment.start()
    while experiment.fitSessions>0:
        socketio.sleep(0.1)
        res=experiment.trainThreadStep1()
        if res=="wait":
            continue
        if type(res) is str:
            print(res)
            socketio.emit('message', success(res), namespace="/pushDeeplink")
            break
    if experiment.fitSessions>0:
        res=experiment.trainThreadStep2()
    while True:
        res=experiment.predictThread()
        if res=="wait":
            continue
        if type(res) is str:
            print(res)
            socketio.emit('message',success(res),namespace="/pushDeeplink")
            break
        res,ctime=res[0],res[2]
        if res==1:
            d=linker.match(ctime)
            socketio.emit('newlinks',success(d[0].toJson()),namespace="/pushDeeplink")
@socketio.on('connect',namespace='/pushDeeplink')
def startDetection():
    global _thread
    try:
        if thread_lock:
            _thread = socketio.start_background_task(target=background_task)
    except Exception as e:
        print(e)
        emit("message",fail(str(e)))
    emit("message",success("开始检测"))

@socketio.on('connect',namespace='/test')
def pushtarget():
    print("here in test connect")
    socketio.emit("relatetarget",success({"message":"1号脑电模块已准备就绪"}),namespace="/admin")
    socketio.emit("relatetarget",success({"message":"计算机视觉模块已准备就绪"}),namespace="/admin")



def eegdataBackTask(c=1):
    global _eegthread,experiment
    socketio.emit('message', success("数据接收通道开启成功"), namespace="/eegdata")
    timeend = -1
    cnt=0
    while _eegthread is not None:
        arr, rend = experiment.getData(timeend, show=True)
        arr=arr[:c]
        if rend != timeend:
            timeend = rend
            socketio.emit('eegdatacome', success(arr.tolist()),namespace="/eegdata")
            cnt=0
        else:
            cnt+=1
            if cnt==20:
                timeend=-1
                cnt=0
        # print("running")
        socketio.sleep(0.05)
@socketio.on('geteegdata',namespace='/eegdata')
def eegsocket(d):
    global _eegthread
    _eegthread=socketio.start_background_task(eegdataBackTask,d['c'])
@socketio.on("stopreceive",namespace='/eegdata')
def closeEEGsocket():
    global _eegthread
    _eegthread=None

@app.route("/api/bcigo")
def bcigo():
    try:
        bciReady()
    except Exception as e:
        print(e)
        return fail(str(e))
    return success({"channels":experiment.channels})

@app.route("/api/bcidown")
def closeBCI():
    global experiment
    experiment.finish(savefile=True)
    return success()

@app.route("/api/reIdgo")
def reIDgo():
    try:
        reIDReady()
    except Exception as e:
        print(e)
        return fail(str(e))
    return success()


'''准备脑电接口'''
def bciReady(filename='config.ini'):
    global experiment
    if experiment!=None:
        experiment.finish()
    conf.read(filename)
    experiment=Experiment()
    cur=conf['experiment']
    sessions=int(cur['session'])
    fitSessions=int(cur['fitsessions'])
    trials=int(cur['trials'])
    duration=int(cur['duration'])
    interval=int(cur['interval'])
    tmin=int(cur['tmin'])
    tmax=int(cur['tmax'])
    device=int(cur['device'])
    skipinterval=int(cur['skipinterval'])
    experiment.setParameters(sessions,fitSessions,trials,duration,interval,tmin,tmax,device,skipinterval)
    print("实验创建成功")
    
    cur=conf['filter']
    sampleRateFrom=int(cur['sampleRateFrom'])
    sampleRateTo=int(cur['sampleRateTo'])
    low=float(cur['low'])
    high=float(cur['high'])
    channels=cur['channels'].split(',')
    idxs=experiment.set_channel(channels)
    mfilter=BciFilter(low,high,sampleRateFrom,sampleRateTo,idxs)
    experiment.set_filter(mfilter)
    print("滤波-通道选择器初始化成功")
    
    module=importlib.import_module(conf['model']['path'])
    for name in module.getClassName():
        content="globals()['"+name+"']=module."+name
        exec(content)
    experiment.set_classfier(module.getModel())
    print("脑电判别模型准备成功")
    
    cur=conf['bcitcp']
    host=cur['host']
    port=int(cur['port'])
    tcpname=cur['name']
    TCPParse=experiment.getParse()
    tcp=TCPParse(host=host,port=port,name=tcpname)
    print("tcp: ",tcp)
    ch_nums=experiment.device_channels
    tcp.create_batch(ch_nums)
    experiment.set_dataIn(tcp)
    experiment.start_tcp() #start To SaveData
    print("脑电数据接入成功")
'''准备REID接口'''
def reIDReady(filename='config.ini'):
    global reID
    conf.read(filename)
    cur=conf['reidtcp']
    reID=ReIDTCP(host=cur['host'],port=int(cur['port']))
if __name__=='__main__':    
    socketio.run(app, host='0.0.0.0',port=80, debug=False)

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


def background_task():
    global linker,experiment,reID
    experiment.start()
    while experiment.fitSessions>0:
        socketio.sleep(0.1)
        res=experiment.trainThreadStep1()
        if res=="wait":
            continue
        if type(res) is str:
            print(res)
            socketio.emit('my_response',success({"finish":1,"message":res}))
            break
        socketio.emit('my_response',success({"finish":0,"sessions":res[0],"trials":res[1]}))
    if experiment.fitSessions>0:
        res=experiment.trainThreadStep2()
        socketio.emit('my_response',success({"finish":1,"message":res}))
    while True:
        res=experiment.predictThread()
        if res=="wait":
            continue
        if type(res) is str:
            print(res)
            socketio.emit('my_response',success({"finish":1,"message":res}))
            break
        res,ctime=res[0],res[2]
        if res==1:
            d=linker.match(ctime)
            if type(d) is list:
                if reID is not None:
                    d=reID.getMoreVideo(d)
                socketio.emit('newdeeplinks',success({"deeplinks":[item.toJson() for item in d]}))
@app.route('/')
def page1():
    return render_template("video.html")
@app.route('/admin')
def pageAdmin():
    return render_template("admin.html", async_mode=socketio.async_mode)

@socketio.on('connect',namespace='/pushDeeplink')
def recevDeepLink(jsondata):
    print(type(jsondata))
    print(jsondata)
    model=VideoDeepLink
    for (key,value) in jsondata.items():
        model.__setattr__(key,value)
    linker.append(model)
    emit("receive",success({"finish":1,"message":"接受成功"}))
@socketio.on('connect',namespace='/test')
def pushtarget():
    print("here in test connect")
    socketio.emit("relatetarget",success({"message":"1号脑电模块已准备就绪"}),namespace="/admin")
    socketio.emit("relatetarget",success({"message":"计算机视觉模块已准备就绪"}),namespace="/admin")

@socketio.on('startDetection')
def startDetection():
    global _thread
    try:
        if thread_lock:
            _thread = socketio.start_background_task(target=background_task)
    except Exception as e:
        print(e)
        emit("my_response",fail(str(e)))
    emit("my_response",success())
def eegdataBackTask(c=1):
    global _eegthread,experiment
    socketio.emit('message', success("数据接收通道开启成功"), namespace="/eegdata")
    timeend = -1
    while _eegthread is not None:
        arr, rend = experiment.getData(timeend, show=True)
        arr=arr[:c]
        if rend != timeend:
            timeend = rend
            socketio.emit('eegdatacome', success(arr.tolist()),namespace="/eegdata")
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
    experiment.finish(savefile=False)
    return success()

@app.route("/api/reIdgo") 
def reIDgo():
    try:
        reIDReady()
    except Exception as e:
        print(e)
        return fail(str(e))
    return success()

@app.route('/api/getdata')
def getdata():
    global experiment
    # print("TCP END WHEN GET DATA",experiment.tcp.end)
    try:
        timeend=int(request.args.get('timeend'))
        arr,rend=experiment.getData(timeend,show=True)
        # print(arr.tolist())
    except Exception as e:
        traceback.print_exc()
        return fail(str(e))
    # print("返回数据维度：", np.array(arr).shape)
    # print(np.array(arr).shape)
    # ['Fz','Cz','Pz','P3','P4','P7','P8','Oz','O1','O2','T7','T8']
    return success({"data":arr.tolist(),'timeend':rend})
    
@app.route("/api/reviseBaseline")
def reviseBaseline():
    global experiment
    try:
        experiment.reviseBaseline()
    except Exception as e:
        print(e)
        return fail(str(e))
    return success("修正基线成功")



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

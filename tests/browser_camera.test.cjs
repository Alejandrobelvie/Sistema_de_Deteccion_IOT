// Lifecycle checks without opening a real camera or requiring a browser package.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function workspace(getUserMedia, enumerateDevices = async()=>[{kind:'videoinput',deviceId:'device-1',label:'Laptop <camera>'}]) {
  const elements = new Map();
  function element(selector) {
    if (!elements.has(selector)) elements.set(selector, {
      textContent: '', innerHTML: '', hidden: false, open: false, isConnected: true,
      style: {}, events: {}, classList: {toggle() {}},
      setAttribute() {}, removeAttribute() {}, append() {},
      showModal() {this.open = true;},
      close() {this.open = false;this.events.close?.();},
      addEventListener(name, fn) {this.events[name] = fn;},
      play: async () => {},
    });
    return elements.get(selector);
  }
  const context = vm.createContext({
    document: {querySelector:element,querySelectorAll:()=>[],addEventListener(){}},
    window:{isSecureContext:true,addEventListener(){}},
    navigator:{mediaDevices:{getUserMedia,enumerateDevices}},
    sessionStorage:{getItem:()=>null,removeItem(){},setItem(){}},
    location:{hash:'#home'},URL:{revokeObjectURL(){},createObjectURL:()=> 'blob:recording'},Blob,Intl,Date,setTimeout,clearTimeout,
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/web/app.js'),'utf8'), context);
  return {context,element,run:code=>vm.runInContext(code,context)};
}
const tick = () => new Promise(resolve=>setImmediate(resolve));

test('camera closes its tracks and escapes device labels',async()=>{
  let stopped=0;
  const track={stop(){stopped++;},getSettings:()=>({deviceId:'device-1'})};
  const stream={getTracks:()=>[track],getVideoTracks:()=>[track]};
  const app=workspace(async()=>stream);
  app.run('browserCamera()');await tick();
  assert.equal(app.element('#browser-video').srcObject,stream);
  assert.match(app.element('#browser-device').innerHTML,/Laptop &lt;camera&gt;/);
  app.element('#modal').close();
  assert.equal(stopped,1);
});

test('permission resolving after close immediately releases its stream',async()=>{
  let resolvePermission,stopped=0;
  const track={stop(){stopped++;}};
  const app=workspace(()=>new Promise(resolve=>resolvePermission=resolve));
  app.run('browserCamera()');
  app.element('#modal').close();
  resolvePermission({getTracks:()=>[track]});await tick();
  assert.equal(stopped,1);
  assert.equal(app.element('#browser-video').srcObject,undefined);
});

test('insecure phone URL displays HTTPS instructions without requesting capture',()=>{
  let requested=false;
  const app=workspace(()=>{requested=true;});
  app.run('window.isSecureContext=false; browserCamera()');
  assert.equal(requested,false);
  assert.match(app.element('#browser-status').textContent,/HTTPS/);
});

test('selecting another camera stops the old stream and requests the selected device',async()=>{
  const requested=[],stopped=[];
  const makeStream=id=>{
    const track={stop(){stopped.push(id);},getSettings:()=>({deviceId:id}),onended:null};
    return {getTracks:()=>[track],getVideoTracks:()=>[track]};
  };
  const app=workspace(async constraints=>{
    const id=constraints.video.deviceId?.exact||'device-1';requested.push(constraints);return makeStream(id);
  },async()=>[
    {kind:'videoinput',deviceId:'device-1',label:'Front camera'},
    {kind:'videoinput',deviceId:'device-2',label:'Rear camera'},
  ]);
  app.run('browserCamera()');await tick();
  assert.equal(app.element('#browser-device').disabled,false);
  app.element('#browser-device').onchange({target:{value:'device-2'}});await tick();
  assert.equal(requested[1].video.deviceId.exact,'device-2');
  assert.deepEqual(stopped,['device-1']);
  assert.equal(app.element('#browser-video').srcObject.getVideoTracks()[0].getSettings().deviceId,'device-2');
  assert.match(app.element('#browser-status').textContent,/connected/);
});

test('registered camera recording can pause, resume, stop, and be deleted',()=>{
  let stopped=0,revoked=0;
  class Recorder {
    static isTypeSupported(){return true;}
    constructor(stream,options){this.stream=stream;this.mimeType=options.mimeType;this.state='inactive';}
    start(){this.state='recording';}
    pause(){this.state='paused';}
    resume(){this.state='recording';}
    stop(){this.state='inactive';this.onstop?.();}
  }
  const app=workspace(async()=>{}),track={stop(){stopped++;}},stream={getTracks:()=>[track]};
  app.context.MediaRecorder=Recorder;app.context.window.MediaRecorder=Recorder;
  app.context.URL.revokeObjectURL=()=>revoked++;
  const canvas=app.element('[data-feed="7"]');canvas.width=640;canvas.captureStream=()=>stream;
  app.run('startCameraRecording(7)');
  assert.equal(app.run('cameraRecordings.get(7).recorder.state'),'recording');
  app.run('pauseCameraRecording(7)');assert.equal(app.run('cameraRecordings.get(7).recorder.state'),'paused');
  app.run('pauseCameraRecording(7)');assert.equal(app.run('cameraRecordings.get(7).recorder.state'),'recording');
  app.run('stopCameraRecording(7)');assert.match(app.element('[data-recording-result="7"]').innerHTML,/Download video/);
  app.run('deleteCameraRecording(7)');assert.equal(app.run('cameraRecordings.has(7)'),false);
  assert.equal(stopped,2);assert.equal(revoked,1);
});

// Lifecycle checks without opening a real camera or requiring a browser package.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function workspace(getUserMedia) {
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
    navigator:{mediaDevices:{getUserMedia,enumerateDevices:async()=>[{kind:'videoinput',deviceId:'device-1',label:'Laptop <camera>'}]}},
    sessionStorage:{getItem:()=>null,removeItem(){},setItem(){}},
    location:{hash:'#home'},URL:{revokeObjectURL(){}},Intl,Date,setTimeout,
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

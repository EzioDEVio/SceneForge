// In-page dialogs avoid blocking the desktop renderer and restore editing focus.
function ask(message:string, initial?:string):Promise<string|null> {
  if(typeof HTMLDialogElement==='undefined'||!HTMLDialogElement.prototype.showModal){
    return Promise.resolve(initial===undefined?(confirm(message)?'yes':null):window.prompt(message,initial));
  }
  return new Promise(resolve=>{
    const previous=document.activeElement as HTMLElement|null;
    const dialog=document.createElement('dialog');dialog.className='editor-confirm';
    const form=document.createElement('form');form.method='dialog';
    const text=document.createElement('p');text.textContent=message;form.append(text);
    let input:HTMLInputElement|undefined;
    if(initial!==undefined){input=document.createElement('input');input.value=initial;input.setAttribute('aria-label','Value');form.append(input);}
    const actions=document.createElement('div');actions.className='button-row';
    const cancel=document.createElement('button');cancel.textContent='Cancel';cancel.value='cancel';cancel.className='btn';
    const ok=document.createElement('button');ok.textContent='Continue';ok.value='yes';ok.className='btn btn-primary';
    actions.append(cancel,ok);form.append(actions);dialog.append(form);document.body.append(dialog);
    dialog.addEventListener('close',()=>{const result=dialog.returnValue==='yes'?(input?.value??'yes'):null;dialog.remove();if(previous?.isConnected)previous.focus();resolve(result);},{once:true});
    dialog.showModal();(input||cancel).focus();
  });
}
export async function askConfirm(message:string){return (await ask(message))!==null;}
export function askText(message:string,initial:string){return ask(message,initial);}

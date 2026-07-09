import{C as e,O as t,S as n,b as r,c as i,f as a,g as o,h as s,i as c,k as l,l as u,n as d,o as f,t as p,w as m,x as h}from"./PageHeader-CL9q7qjr.js";import{n as g,s as _}from"./Suffix-By10vu9c.js";import{a as v,i as y,t as b}from"./GlossaryTip-BPMTSbkF.js";import{i as x,t as S}from"./JobCard-klu-3HDo.js";import{i as C,t as w}from"./Button-CIFebtpz.js";import{t as T}from"./Select-BZT-P8Q9.js";import{n as E,t as ee}from"./Popconfirm-D5ncB2Y7.js";import{$n as D,$t as te,Bn as O,Cn as k,D as ne,Dn as re,F as ie,G as ae,Gt as oe,H as se,Hn as A,In as ce,Jt as j,K as le,Kn as M,Ln as N,Nn as P,Q as ue,Qn as de,R as fe,Rn as F,S as pe,Sr as I,Tn as me,Un as L,Vn as R,W as he,Wn as z,Wt as ge,X as _e,Xn as ve,Xt as ye,Yn as be,Zt as xe,_ as Se,_n as B,a as Ce,ar as we,bn as V,d as Te,dr as H,f as Ee,fr as De,gn as Oe,hn as ke,hr as U,i as Ae,in as je,ir as W,kn as Me,lr as G,mr as Ne,n as Pe,nr as Fe,o as Ie,on as Le,or as K,pn as Re,q as ze,qn as Be,r as Ve,rn as He,s as q,sn as Ue,t as We,tr as Ge,tt as Ke,u as qe,vn as J,vr as Je,wn as Ye,wr as Y,x as Xe,xn as X,xr as Z,zn as Ze}from"./index-D2m1fciL.js";var Qe=U(null);function $e(e){if(e.clientX>0||e.clientY>0)Qe.value={x:e.clientX,y:e.clientY};else{let{target:t}=e;if(t instanceof Element){let{left:e,top:n,width:r,height:i}=t.getBoundingClientRect();e>0||n>0?Qe.value={x:e+r/2,y:n+i/2}:Qe.value={x:0,y:0}}else Qe.value=null}}var et=0,tt=!0;function nt(){if(!l)return Ne(U(null));et===0&&Ue(`click`,document,$e,!0);let e=()=>{et+=1};return(tt&&=t())?(de(e),D(()=>{--et,et===0&&Le(`click`,document,$e,!0)})):e(),Ne(Qe)}var rt=U(void 0),it=0;function at(){rt.value=Date.now()}var ot=!0;function st(e){if(!l)return Ne(U(!1));let n=U(!1),r=null;function i(){r!==null&&window.clearTimeout(r)}function a(){i(),n.value=!0,r=window.setTimeout(()=>{n.value=!1},e)}it===0&&Ue(`click`,window,at,!0);let o=()=>{it+=1,Ue(`click`,window,a,!0)};return(ot&&=t())?(de(o),D(()=>{--it,it===0&&Le(`click`,window,at,!0),Le(`click`,window,a,!0),i()})):o(),Ne(n)}var ct=U(!1);function lt(){ct.value=!0}function ut(){ct.value=!1}var dt=0;function ft(){return C&&(de(()=>{dt||(window.addEventListener(`compositionstart`,lt),window.addEventListener(`compositionend`,ut)),dt++}),D(()=>{dt<=1?(window.removeEventListener(`compositionstart`,lt),window.removeEventListener(`compositionend`,ut),dt=0):dt--})),ct}var pt=0,mt=``,ht=``,gt=``,_t=``,vt=U(`0px`);function yt(e){if(typeof document>`u`)return;let t=document.documentElement,n,r=!1,i=()=>{t.style.marginRight=mt,t.style.overflow=ht,t.style.overflowX=gt,t.style.overflowY=_t,vt.value=`0px`};Ge(()=>{n=G(e,e=>{if(e){if(!pt){let e=window.innerWidth-t.offsetWidth;e>0&&(mt=t.style.marginRight,t.style.marginRight=`${e}px`,vt.value=`${e}px`),ht=t.style.overflow,gt=t.style.overflowX,_t=t.style.overflowY,t.style.overflow=`hidden`,t.style.overflowX=`hidden`,t.style.overflowY=`hidden`}r=!0,pt++}else pt--,pt||i(),r=!1},{immediate:!0})}),D(()=>{n?.(),r&&=(pt--,pt||i(),!1)})}var bt=J(`card-content`,`
 flex: 1;
 min-width: 0;
 box-sizing: border-box;
 padding: 0 var(--n-padding-left) var(--n-padding-bottom) var(--n-padding-left);
 font-size: var(--n-font-size);
`),xt=B([J(`card`,`
 font-size: var(--n-font-size);
 line-height: var(--n-line-height);
 display: flex;
 flex-direction: column;
 width: 100%;
 box-sizing: border-box;
 position: relative;
 border-radius: var(--n-border-radius);
 background-color: var(--n-color);
 color: var(--n-text-color);
 word-break: break-word;
 transition: 
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `,[Oe({background:`var(--n-color-modal)`}),X(`hoverable`,[B(`&:hover`,`box-shadow: var(--n-box-shadow);`)]),X(`content-segmented`,[B(`>`,[J(`card-content`,`
 padding-top: var(--n-padding-bottom);
 `),V(`content-scrollbar`,[B(`>`,[J(`scrollbar-container`,[B(`>`,[J(`card-content`,`
 padding-top: var(--n-padding-bottom);
 `)])])])])])]),X(`content-soft-segmented`,[B(`>`,[J(`card-content`,`
 margin: 0 var(--n-padding-left);
 padding: var(--n-padding-bottom) 0;
 `),V(`content-scrollbar`,[B(`>`,[J(`scrollbar-container`,[B(`>`,[J(`card-content`,`
 margin: 0 var(--n-padding-left);
 padding: var(--n-padding-bottom) 0;
 `)])])])])])]),X(`footer-segmented`,[B(`>`,[V(`footer`,`
 padding-top: var(--n-padding-bottom);
 `)])]),X(`footer-soft-segmented`,[B(`>`,[V(`footer`,`
 padding: var(--n-padding-bottom) 0;
 margin: 0 var(--n-padding-left);
 `)])]),B(`>`,[J(`card-header`,`
 box-sizing: border-box;
 display: flex;
 align-items: center;
 font-size: var(--n-title-font-size);
 padding:
 var(--n-padding-top)
 var(--n-padding-left)
 var(--n-padding-bottom)
 var(--n-padding-left);
 `,[V(`main`,`
 font-weight: var(--n-title-font-weight);
 transition: color .3s var(--n-bezier);
 flex: 1;
 min-width: 0;
 color: var(--n-title-text-color);
 `),V(`extra`,`
 display: flex;
 align-items: center;
 font-size: var(--n-font-size);
 font-weight: 400;
 transition: color .3s var(--n-bezier);
 color: var(--n-text-color);
 `),V(`close`,`
 margin: 0 0 0 8px;
 transition:
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 `)]),V(`action`,`
 box-sizing: border-box;
 transition:
 background-color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 background-clip: padding-box;
 background-color: var(--n-action-color);
 `),bt,J(`card-content`,[B(`&:first-child`,`
 padding-top: var(--n-padding-bottom);
 `)]),V(`content-scrollbar`,`
 display: flex;
 flex-direction: column;
 `,[B(`>`,[J(`scrollbar-container`,[B(`>`,[bt])])]),B(`&:first-child >`,[J(`scrollbar-container`,[B(`>`,[J(`card-content`,`
 padding-top: var(--n-padding-bottom);
 `)])])])]),V(`footer`,`
 box-sizing: border-box;
 padding: 0 var(--n-padding-left) var(--n-padding-bottom) var(--n-padding-left);
 font-size: var(--n-font-size);
 `,[B(`&:first-child`,`
 padding-top: var(--n-padding-bottom);
 `)]),V(`action`,`
 background-color: var(--n-action-color);
 padding: var(--n-padding-bottom) var(--n-padding-left);
 border-bottom-left-radius: var(--n-border-radius);
 border-bottom-right-radius: var(--n-border-radius);
 `)]),J(`card-cover`,`
 overflow: hidden;
 width: 100%;
 border-radius: var(--n-border-radius) var(--n-border-radius) 0 0;
 `,[B(`img`,`
 display: block;
 width: 100%;
 `)]),X(`bordered`,`
 border: 1px solid var(--n-border-color);
 `,[B(`&:target`,`border-color: var(--n-color-target);`)]),X(`action-segmented`,[B(`>`,[V(`action`,[B(`&:not(:first-child)`,`
 border-top: 1px solid var(--n-border-color);
 `)])])]),X(`content-segmented, content-soft-segmented`,[B(`>`,[J(`card-content`,`
 transition: border-color 0.3s var(--n-bezier);
 `,[B(`&:not(:first-child)`,`
 border-top: 1px solid var(--n-border-color);
 `)]),V(`content-scrollbar`,`
 transition: border-color 0.3s var(--n-bezier);
 `,[B(`&:not(:first-child)`,`
 border-top: 1px solid var(--n-border-color);
 `)])])]),X(`footer-segmented, footer-soft-segmented`,[B(`>`,[V(`footer`,`
 transition: border-color 0.3s var(--n-bezier);
 `,[B(`&:not(:first-child)`,`
 border-top: 1px solid var(--n-border-color);
 `)])])]),X(`embedded`,`
 background-color: var(--n-color-embedded);
 `)]),Ye(J(`card`,`
 background: var(--n-color-modal);
 `,[X(`embedded`,`
 background-color: var(--n-color-embedded-modal);
 `)])),me(J(`card`,`
 background: var(--n-color-popover);
 `,[X(`embedded`,`
 background-color: var(--n-color-embedded-popover);
 `)]))]),St={title:[String,Function],contentClass:String,contentStyle:[Object,String],contentScrollable:Boolean,headerClass:String,headerStyle:[Object,String],headerExtraClass:String,headerExtraStyle:[Object,String],footerClass:String,footerStyle:[Object,String],embedded:Boolean,segmented:{type:[Boolean,Object],default:!1},size:String,bordered:{type:Boolean,default:!0},closable:Boolean,hoverable:Boolean,role:String,onClose:[Function,Array],tag:{type:String,default:`div`},cover:Function,content:[String,Function],footer:Function,action:Function,headerExtra:Function,closeFocusable:Boolean},Ct=ye(St),wt=z({name:`Card`,props:Object.assign(Object.assign({},ue.props),St),slots:Object,setup(e){let t=()=>{let{onClose:t}=e;t&&u(t)},{inlineThemeDisabled:n,mergedClsPrefixRef:r,mergedRtlRef:i,mergedComponentPropsRef:a}=oe(e),o=ue(`Card`,`-card`,xt,ne,e,r),s=Ke(`Card`,i,r),c=N(()=>e.size||a?.value?.Card?.size||`medium`),l=N(()=>{let e=c.value,{self:{color:t,colorModal:n,colorTarget:r,textColor:i,titleTextColor:a,titleFontWeight:s,borderColor:l,actionColor:u,borderRadius:d,lineHeight:f,closeIconColor:p,closeIconColorHover:m,closeIconColorPressed:h,closeColorHover:g,closeColorPressed:_,closeBorderRadius:v,closeIconSize:y,closeSize:b,boxShadow:x,colorPopover:S,colorEmbedded:C,colorEmbeddedModal:w,colorEmbeddedPopover:T,[k(`padding`,e)]:E,[k(`fontSize`,e)]:ee,[k(`titleFontSize`,e)]:D},common:{cubicBezierEaseInOut:te}}=o.value,{top:O,left:ne,bottom:re}=Re(E);return{"--n-bezier":te,"--n-border-radius":d,"--n-color":t,"--n-color-modal":n,"--n-color-popover":S,"--n-color-embedded":C,"--n-color-embedded-modal":w,"--n-color-embedded-popover":T,"--n-color-target":r,"--n-text-color":i,"--n-line-height":f,"--n-action-color":u,"--n-title-text-color":a,"--n-title-font-weight":s,"--n-close-icon-color":p,"--n-close-icon-color-hover":m,"--n-close-icon-color-pressed":h,"--n-close-color-hover":g,"--n-close-color-pressed":_,"--n-border-color":l,"--n-box-shadow":x,"--n-padding-top":O,"--n-padding-bottom":re,"--n-padding-left":ne,"--n-font-size":ee,"--n-title-font-size":D,"--n-close-size":b,"--n-close-icon-size":y,"--n-close-border-radius":v}}),d=n?ge(`card`,N(()=>c.value[0]),l,e):void 0;return{rtlEnabled:s,mergedClsPrefix:r,mergedTheme:o,handleCloseClick:t,cssVars:n?void 0:l,themeClass:d?.themeClass,onRender:d?.onRender}},render(){let{segmented:e,bordered:t,hoverable:n,mergedClsPrefix:r,rtlEnabled:a,onRender:o,embedded:s,tag:l,$slots:u}=this;return o?.(),M(l,{class:[`${r}-card`,this.themeClass,s&&`${r}-card--embedded`,{[`${r}-card--rtl`]:a,[`${r}-card--content-scrollable`]:this.contentScrollable,[`${r}-card--content${typeof e!=`boolean`&&e.content===`soft`?`-soft`:``}-segmented`]:e===!0||e!==!1&&e.content,[`${r}-card--footer${typeof e!=`boolean`&&e.footer===`soft`?`-soft`:``}-segmented`]:e===!0||e!==!1&&e.footer,[`${r}-card--action-segmented`]:e===!0||e!==!1&&e.action,[`${r}-card--bordered`]:t,[`${r}-card--hoverable`]:n}],style:this.cssVars,role:this.role},i(u.cover,e=>{let t=this.cover?c([this.cover()]):e;return t&&M(`div`,{class:`${r}-card-cover`,role:`none`},t)}),i(u.header,e=>{let{title:t}=this,n=t?c(typeof t==`function`?[t()]:[t]):e;return n||this.closable?M(`div`,{class:[`${r}-card-header`,this.headerClass],style:this.headerStyle,role:`heading`},M(`div`,{class:`${r}-card-header__main`,role:`heading`},n),i(u[`header-extra`],e=>{let t=this.headerExtra?c([this.headerExtra()]):e;return t&&M(`div`,{class:[`${r}-card-header__extra`,this.headerExtraClass],style:this.headerExtraStyle},t)}),this.closable&&M(se,{clsPrefix:r,class:`${r}-card-header__close`,onClick:this.handleCloseClick,focusable:this.closeFocusable,absolute:!0})):null}),i(u.default,e=>{let{content:t}=this,n=t?c(typeof t==`function`?[t()]:[t]):e;return n?this.contentScrollable?M(ie,{class:`${r}-card__content-scrollbar`,contentClass:[`${r}-card-content`,this.contentClass],contentStyle:this.contentStyle},n):M(`div`,{class:[`${r}-card-content`,this.contentClass],style:this.contentStyle,role:`none`},n):null}),i(u.footer,e=>{let t=this.footer?c([this.footer()]):e;return t&&M(`div`,{class:[`${r}-card__footer`,this.footerClass],style:this.footerStyle,role:`none`},t)}),i(u.action,e=>{let t=this.action?c([this.action()]):e;return t&&M(`div`,{class:`${r}-card__action`,role:`none`},t)}))}}),Tt=He(`n-dialog-provider`);He(`n-dialog-api`),He(`n-dialog-reactive-list`);var Et={icon:Function,type:{type:String,default:`default`},title:[String,Function],closable:{type:Boolean,default:!0},negativeText:String,positiveText:String,positiveButtonProps:Object,negativeButtonProps:Object,content:[String,Function],action:Function,showIcon:{type:Boolean,default:!0},loading:Boolean,bordered:Boolean,iconPlacement:String,titleClass:[String,Array],titleStyle:[String,Object],contentClass:[String,Array],contentStyle:[String,Object],actionClass:[String,Array],actionStyle:[String,Object],onPositiveClick:Function,onNegativeClick:Function,onClose:Function,closeFocusable:Boolean},Dt=ye(Et),Ot=B([J(`dialog`,`
 --n-icon-margin: var(--n-icon-margin-top) var(--n-icon-margin-right) var(--n-icon-margin-bottom) var(--n-icon-margin-left);
 word-break: break-word;
 line-height: var(--n-line-height);
 position: relative;
 background: var(--n-color);
 color: var(--n-text-color);
 box-sizing: border-box;
 margin: auto;
 border-radius: var(--n-border-radius);
 padding: var(--n-padding);
 transition: 
 border-color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 `,[V(`icon`,`
 color: var(--n-icon-color);
 `),X(`bordered`,`
 border: var(--n-border);
 `),X(`icon-top`,[V(`close`,`
 margin: var(--n-close-margin);
 `),V(`icon`,`
 margin: var(--n-icon-margin);
 `),V(`content`,`
 text-align: center;
 `),V(`title`,`
 justify-content: center;
 `),V(`action`,`
 justify-content: center;
 `)]),X(`icon-left`,[V(`icon`,`
 margin: var(--n-icon-margin);
 `),X(`closable`,[V(`title`,`
 padding-right: calc(var(--n-close-size) + 6px);
 `)])]),V(`close`,`
 position: absolute;
 right: 0;
 top: 0;
 margin: var(--n-close-margin);
 transition:
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 z-index: 1;
 `),V(`content`,`
 font-size: var(--n-font-size);
 margin: var(--n-content-margin);
 position: relative;
 word-break: break-word;
 `,[X(`last`,`margin-bottom: 0;`)]),V(`action`,`
 display: flex;
 justify-content: flex-end;
 `,[B(`> *:not(:last-child)`,`
 margin-right: var(--n-action-space);
 `)]),V(`icon`,`
 font-size: var(--n-icon-size);
 transition: color .3s var(--n-bezier);
 `),V(`title`,`
 transition: color .3s var(--n-bezier);
 display: flex;
 align-items: center;
 font-size: var(--n-title-font-size);
 font-weight: var(--n-title-font-weight);
 color: var(--n-title-text-color);
 `),J(`dialog-icon-container`,`
 display: flex;
 justify-content: center;
 `)]),Ye(J(`dialog`,`
 width: 446px;
 max-width: calc(100vw - 32px);
 `)),J(`dialog`,[Oe(`
 width: 446px;
 max-width: calc(100vw - 32px);
 `)])]),kt={default:()=>M(le,null),info:()=>M(le,null),success:()=>M(ae,null),warning:()=>M(he,null),error:()=>M(ze,null)},At=z({name:`Dialog`,alias:[`NimbusConfirmCard`,`Confirm`],props:Object.assign(Object.assign({},ue.props),Et),slots:Object,setup(e){let{mergedComponentPropsRef:t,mergedClsPrefixRef:n,inlineThemeDisabled:r,mergedRtlRef:i}=oe(e),a=Ke(`Dialog`,i,n),o=N(()=>{let{iconPlacement:n}=e;return n||t?.value?.Dialog?.iconPlacement||`left`});function s(t){let{onPositiveClick:n}=e;n&&n(t)}function c(t){let{onNegativeClick:n}=e;n&&n(t)}function l(){let{onClose:t}=e;t&&t()}let u=ue(`Dialog`,`-dialog`,Ot,pe,e,n),d=N(()=>{let{type:t}=e,n=o.value,{common:{cubicBezierEaseInOut:r},self:{fontSize:i,lineHeight:a,border:s,titleTextColor:c,textColor:l,color:d,closeBorderRadius:f,closeColorHover:p,closeColorPressed:m,closeIconColor:h,closeIconColorHover:g,closeIconColorPressed:_,closeIconSize:v,borderRadius:y,titleFontWeight:b,titleFontSize:x,padding:S,iconSize:C,actionSpace:w,contentMargin:T,closeSize:E,[n===`top`?`iconMarginIconTop`:`iconMargin`]:ee,[n===`top`?`closeMarginIconTop`:`closeMargin`]:D,[k(`iconColor`,t)]:te}}=u.value,O=Re(ee);return{"--n-font-size":i,"--n-icon-color":te,"--n-bezier":r,"--n-close-margin":D,"--n-icon-margin-top":O.top,"--n-icon-margin-right":O.right,"--n-icon-margin-bottom":O.bottom,"--n-icon-margin-left":O.left,"--n-icon-size":C,"--n-close-size":E,"--n-close-icon-size":v,"--n-close-border-radius":f,"--n-close-color-hover":p,"--n-close-color-pressed":m,"--n-close-icon-color":h,"--n-close-icon-color-hover":g,"--n-close-icon-color-pressed":_,"--n-color":d,"--n-text-color":l,"--n-border-radius":y,"--n-padding":S,"--n-line-height":a,"--n-border":s,"--n-content-margin":T,"--n-title-font-size":x,"--n-title-font-weight":b,"--n-title-text-color":c,"--n-action-space":w}}),f=r?ge(`dialog`,N(()=>`${e.type[0]}${o.value[0]}`),d,e):void 0;return{mergedClsPrefix:n,rtlEnabled:a,mergedIconPlacement:o,mergedTheme:u,handlePositiveClick:s,handleNegativeClick:c,handleCloseClick:l,cssVars:r?void 0:d,themeClass:f?.themeClass,onRender:f?.onRender}},render(){var e;let{bordered:t,mergedIconPlacement:n,cssVars:r,closable:a,showIcon:o,title:s,content:c,action:l,negativeText:u,positiveText:d,positiveButtonProps:p,negativeButtonProps:m,handlePositiveClick:h,handleNegativeClick:g,mergedTheme:_,loading:v,type:y,mergedClsPrefix:b}=this;(e=this.onRender)==null||e.call(this);let x=o?M(_e,{clsPrefix:b,class:`${b}-dialog__icon`},{default:()=>i(this.$slots.icon,e=>e||(this.icon?j(this.icon):kt[this.type]()))}):null,S=i(this.$slots.action,e=>e||d||u||l?M(`div`,{class:[`${b}-dialog__action`,this.actionClass],style:this.actionStyle},e||(l?[j(l)]:[this.negativeText&&M(w,Object.assign({theme:_.peers.Button,themeOverrides:_.peerOverrides.Button,ghost:!0,size:`small`,onClick:g},m),{default:()=>j(this.negativeText)}),this.positiveText&&M(w,Object.assign({theme:_.peers.Button,themeOverrides:_.peerOverrides.Button,size:`small`,type:y==="default"?`primary`:y,disabled:v,loading:v,onClick:h},p),{default:()=>j(this.positiveText)})])):null);return M(`div`,{class:[`${b}-dialog`,this.themeClass,this.closable&&`${b}-dialog--closable`,`${b}-dialog--icon-${n}`,t&&`${b}-dialog--bordered`,this.rtlEnabled&&`${b}-dialog--rtl`],style:r,role:`dialog`},a?i(this.$slots.close,e=>{let t=[`${b}-dialog__close`,this.rtlEnabled&&`${b}-dialog--rtl`];return e?M(`div`,{class:t},e):M(se,{focusable:this.closeFocusable,clsPrefix:b,class:t,onClick:this.handleCloseClick})}):null,o&&n===`top`?M(`div`,{class:`${b}-dialog-icon-container`},x):null,M(`div`,{class:[`${b}-dialog__title`,this.titleClass],style:this.titleStyle},o&&n===`left`?x:null,f(this.$slots.header,()=>[j(s)])),M(`div`,{class:[`${b}-dialog__content`,S?``:`${b}-dialog__content--last`,this.contentClass],style:this.contentStyle},f(this.$slots.default,()=>[j(c)])),S)}}),jt=`n-draggable`;function Mt(e,t){let n,r=N(()=>e.value!==!1),i=N(()=>r.value?jt:``),a=N(()=>{let t=e.value;return t===!0||t===!1?!0:t?t.bounds!==`none`:!0});function o(e){let r=e.querySelector(`.${jt}`);if(!r||!i.value)return;let o=0,s=0,c=0,l=0,u=0,d=0,f,p=null,m=null;function h(t){t.preventDefault(),f=t;let{x:n,y:r,right:i,bottom:a}=e.getBoundingClientRect();s=n,l=r,o=window.innerWidth-i,c=window.innerHeight-a;let{left:p,top:m}=e.style;u=+m.slice(0,-2),d=+p.slice(0,-2)}function g(){m&&=(e.style.top=`${m.y}px`,e.style.left=`${m.x}px`,null),p=null}function _(e){if(!f)return;let{clientX:t,clientY:n}=f,r=e.clientX-t,i=e.clientY-n;a.value&&(r>o?r=o:-r>s&&(r=-s),i>c?i=c:-i>l&&(i=-l)),m={x:r+d,y:i+u},p||=requestAnimationFrame(g)}function v(){f=void 0,p&&=(cancelAnimationFrame(p),null),m&&=(e.style.top=`${m.y}px`,e.style.left=`${m.x}px`,null),t.onEnd(e)}Ue(`mousedown`,r,h),Ue(`mousemove`,window,_),Ue(`mouseup`,window,v),n=()=>{p&&cancelAnimationFrame(p),Le(`mousedown`,r,h),Le(`mousemove`,window,_),Le(`mouseup`,window,v)}}function s(){n&&=(n(),void 0)}return Fe(s),{stopDrag:s,startDrag:o,draggableRef:r,draggableClassRef:i}}var Nt=Object.assign(Object.assign({},St),Et),Pt=ye(Nt),Ft=z({name:`ModalBody`,inheritAttrs:!1,slots:Object,props:Object.assign(Object.assign({show:{type:Boolean,required:!0},preset:String,displayDirective:{type:String,required:!0},trapFocus:{type:Boolean,default:!0},autoFocus:{type:Boolean,default:!0},blockScroll:Boolean,draggable:{type:[Boolean,Object],default:!1},maskHidden:Boolean},Nt),{renderMask:Function,onClickoutside:Function,onBeforeLeave:{type:Function,required:!0},onAfterLeave:{type:Function,required:!0},onPositiveClick:{type:Function,required:!0},onNegativeClick:{type:Function,required:!0},onClose:{type:Function,required:!0},onAfterEnter:Function,onEsc:Function}),setup(e){let t=U(null),i=U(null),a=U(e.show),o=U(null),s=U(null),c=Be(n),l=null;G(Je(e,`show`),e=>{e&&(l=c.getMousePosition())},{immediate:!0});let{stopDrag:u,startDrag:d,draggableRef:f,draggableClassRef:p}=Mt(Je(e,`draggable`),{onEnd:e=>{y(e)}}),g=N(()=>I([e.titleClass,p.value])),_=N(()=>I([e.headerClass,p.value]));G(Je(e,`show`),e=>{e&&(a.value=!0)}),yt(N(()=>e.blockScroll&&a.value));function v(){if(c.transformOriginRef.value===`center`)return``;let{value:e}=o,{value:t}=s;return e===null||t===null?``:i.value?`${e}px ${t+i.value.containerScrollTop}px`:``}function y(e){if(c.transformOriginRef.value===`center`||!l||!i.value)return;let t=i.value.containerScrollTop,{offsetLeft:n,offsetTop:r}=e,a=l.y,u=l.x;o.value=-(n-u),s.value=-(r-a-t),e.style.transformOrigin=v()}function b(e){ve(()=>{y(e)})}function x(t){t.style.transformOrigin=v(),e.onBeforeLeave()}function S(t){let n=t;f.value&&d(n),e.onAfterEnter&&e.onAfterEnter(n)}function C(){a.value=!1,o.value=null,s.value=null,u(),e.onAfterLeave()}function w(){let{onClose:t}=e;t&&t()}function T(){e.onNegativeClick()}function E(){e.onPositiveClick()}let ee=U(null);return G(ee,e=>{e&&ve(()=>{let n=e.el;n&&t.value!==n&&(t.value=n)})}),we(h,t),we(m,null),we(r,null),{mergedTheme:c.mergedThemeRef,appear:c.appearRef,isMounted:c.isMountedRef,mergedClsPrefix:c.mergedClsPrefixRef,bodyRef:t,scrollbarRef:i,draggableClass:p,displayed:a,childNodeRef:ee,cardHeaderClass:_,dialogTitleClass:g,handlePositiveClick:E,handleNegativeClick:T,handleCloseClick:w,handleAfterEnter:S,handleAfterLeave:C,handleBeforeLeave:x,handleEnter:b}},render(){let{$slots:e,$attrs:t,handleEnter:n,handleAfterEnter:r,handleAfterLeave:i,handleBeforeLeave:a,preset:s,mergedClsPrefix:c}=this,l=null;if(!s){if(l=y(`default`,e.default,{draggableClass:this.draggableClass}),!l){te(`modal`,`default slot is empty`);return}l=ce(l),l.props=be({class:`${c}-modal`},t,l.props||{})}return this.displayDirective===`show`||this.displayed||this.show?De(M(`div`,{role:`none`,class:[`${c}-modal-body-wrapper`,this.maskHidden&&`${c}-modal-body-wrapper--mask-hidden`]},M(ie,{ref:`scrollbarRef`,theme:this.mergedTheme.peers.Scrollbar,themeOverrides:this.mergedTheme.peerOverrides.Scrollbar,contentClass:`${c}-modal-scroll-content`},{default:()=>[this.renderMask?.call(this),M(v,{disabled:!this.trapFocus||this.maskHidden,active:this.show,onEsc:this.onEsc,autoFocus:this.autoFocus},{default:()=>M(re,{name:`fade-in-scale-up-transition`,appear:this.appear??this.isMounted,onEnter:n,onAfterEnter:r,onAfterLeave:i,onBeforeLeave:a},{default:()=>{let t=[[Me,this.show]],{onClickoutside:n}=this;return n&&t.push([o,this.onClickoutside,void 0,{capture:!0}]),De(this.preset===`confirm`||this.preset===`dialog`?M(At,Object.assign({},this.$attrs,{class:[`${c}-modal`,this.$attrs.class],ref:`bodyRef`,theme:this.mergedTheme.peers.Dialog,themeOverrides:this.mergedTheme.peerOverrides.Dialog},xe(this.$props,Dt),{titleClass:this.dialogTitleClass,"aria-modal":`true`}),e):this.preset===`card`?M(wt,Object.assign({},this.$attrs,{ref:`bodyRef`,class:[`${c}-modal`,this.$attrs.class],theme:this.mergedTheme.peers.Card,themeOverrides:this.mergedTheme.peerOverrides.Card},xe(this.$props,Ct),{headerClass:this.cardHeaderClass,"aria-modal":`true`,role:`dialog`}),e):this.childNodeRef=l,t)}})})]})),[[Me,this.displayDirective===`if`||this.displayed||this.show]]):null}}),It=B([J(`modal-container`,`
 position: fixed;
 left: 0;
 top: 0;
 height: 0;
 width: 0;
 display: flex;
 `),J(`modal-mask`,`
 position: fixed;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 background-color: rgba(0, 0, 0, .4);
 `,[fe({enterDuration:`.25s`,leaveDuration:`.25s`,enterCubicBezier:`var(--n-bezier-ease-out)`,leaveCubicBezier:`var(--n-bezier-ease-out)`})]),J(`modal-body-wrapper`,`
 position: fixed;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 overflow: visible;
 `,[J(`modal-scroll-content`,`
 min-height: 100%;
 display: flex;
 position: relative;
 `),X(`mask-hidden`,`pointer-events: none;`,[J(`modal-scroll-content`,[B(`> *`,`
 pointer-events: all;
 `)])])]),J(`modal`,`
 position: relative;
 align-self: center;
 color: var(--n-text-color);
 margin: auto;
 box-shadow: var(--n-box-shadow);
 `,[g({duration:`.25s`,enterScale:`.5`}),B(`.${jt}`,`
 cursor: move;
 user-select: none;
 `)])]),Lt=z({name:`Modal`,inheritAttrs:!1,props:Object.assign(Object.assign(Object.assign(Object.assign({},ue.props),{show:Boolean,showMask:{type:Boolean,default:!0},maskClosable:{type:Boolean,default:!0},preset:String,to:[String,Object],displayDirective:{type:String,default:`if`},transformOrigin:{type:String,default:`mouse`},zIndex:Number,autoFocus:{type:Boolean,default:!0},trapFocus:{type:Boolean,default:!0},closeOnEsc:{type:Boolean,default:!0},blockScroll:{type:Boolean,default:!0}}),Nt),{draggable:[Boolean,Object],onEsc:Function,"onUpdate:show":[Function,Array],onUpdateShow:[Function,Array],onAfterEnter:Function,onBeforeLeave:Function,onAfterLeave:Function,onClose:Function,onPositiveClick:Function,onNegativeClick:Function,onMaskClick:Function,internalDialog:Boolean,internalModal:Boolean,internalAppear:{type:Boolean,default:void 0},overlayStyle:[String,Object],onBeforeHide:Function,onAfterHide:Function,onHide:Function,unstableShowMask:{type:Boolean,default:void 0}}),slots:Object,setup(t){let r=U(null),{mergedClsPrefixRef:i,namespaceRef:a,inlineThemeDisabled:o}=oe(t),s=ue(`Modal`,`-modal`,It,Xe,t,i),c=st(64),l=nt(),d=je(),f=t.internalDialog?Be(Tt,null):null,p=t.internalModal?Be(e,null):null,m=ft();function h(e){let{onUpdateShow:n,"onUpdate:show":r,onHide:i}=t;n&&u(n,e),r&&u(r,e),i&&!e&&i(e)}function g(){let{onClose:e}=t;e?Promise.resolve(e()).then(e=>{e!==!1&&h(!1)}):h(!1)}function v(){let{onPositiveClick:e}=t;e?Promise.resolve(e()).then(e=>{e!==!1&&h(!1)}):h(!1)}function y(){let{onNegativeClick:e}=t;e?Promise.resolve(e()).then(e=>{e!==!1&&h(!1)}):h(!1)}function b(){let{onBeforeLeave:e,onBeforeHide:n}=t;e&&u(e),n&&n()}function x(){let{onAfterLeave:e,onAfterHide:n}=t;e&&u(e),n&&n()}function S(e){let{onMaskClick:n}=t;n&&n(e),t.maskClosable&&r.value?.contains(ke(e))&&h(!1)}function C(e){var n;(n=t.onEsc)==null||n.call(t),t.show&&t.closeOnEsc&&_(e)&&(m.value||h(!1))}we(n,{getMousePosition:()=>{let e=f||p;if(e){let{clickedRef:t,clickedPositionRef:n}=e;if(t.value&&n.value)return n.value}return c.value?l.value:null},mergedClsPrefixRef:i,mergedThemeRef:s,isMountedRef:d,appearRef:Je(t,`internalAppear`),transformOriginRef:Je(t,`transformOrigin`)});let w=N(()=>{let{common:{cubicBezierEaseOut:e},self:{boxShadow:t,color:n,textColor:r}}=s.value;return{"--n-bezier-ease-out":e,"--n-box-shadow":t,"--n-color":n,"--n-text-color":r}}),T=o?ge(`theme-class`,void 0,w,t):void 0;return{mergedClsPrefix:i,namespace:a,isMounted:d,containerRef:r,presetProps:N(()=>xe(t,Pt)),handleEsc:C,handleAfterLeave:x,handleClickoutside:S,handleBeforeLeave:b,doUpdateShow:h,handleNegativeClick:y,handlePositiveClick:v,handleCloseClick:g,cssVars:o?void 0:w,themeClass:T?.themeClass,onRender:T?.onRender}},render(){let{mergedClsPrefix:e}=this;return M(a,{to:this.to,show:this.show},{default:()=>{var t;(t=this.onRender)==null||t.call(this);let{showMask:n}=this;return De(M(`div`,{role:`none`,ref:`containerRef`,class:[`${e}-modal-container`,this.themeClass,this.namespace],style:this.cssVars},M(Ft,Object.assign({style:this.overlayStyle},this.$attrs,{ref:`bodyWrapper`,displayDirective:this.displayDirective,show:this.show,preset:this.preset,autoFocus:this.autoFocus,trapFocus:this.trapFocus,draggable:this.draggable,blockScroll:this.blockScroll,maskHidden:!n},this.presetProps,{onEsc:this.handleEsc,onClose:this.handleCloseClick,onNegativeClick:this.handleNegativeClick,onPositiveClick:this.handlePositiveClick,onBeforeLeave:this.handleBeforeLeave,onAfterEnter:this.onAfterEnter,onAfterLeave:this.handleAfterLeave,onClickoutside:n?void 0:this.handleClickoutside,renderMask:n?()=>M(re,{name:`fade-in-transition`,key:`mask`,appear:this.internalAppear??this.isMounted},{default:()=>this.show?M(`div`,{"aria-hidden":!0,ref:`containerRef`,class:`${e}-modal-mask`,onClick:this.handleClickoutside}):null}):void 0}),this.$slots)),[[s,{zIndex:this.zIndex,enabled:this.show}]])}})}}),Rt=new Set([`top_excess_return`,`oos_top_excess_return`,`long_short_return`,`oos_long_short_return`]);function zt(e){return Rt.has(e)?`market`:`neutral`}function Bt(e,t){return t==null||zt(e)!==`market`?``:t>0?`t-up`:t<0?`t-down`:``}function Q(e,t,n){return{text:t==null?`-`:n(t),cls:Bt(e,t)}}var Vt={class:`fc-head`},Ht={class:`fc-id-name`},Ut={class:`fid num`},Wt={class:`fname`},Gt={key:1,class:`grade-badge grade-na`,"data-testid":`verdict-card-grade`},Kt={class:`fc-metrics`},qt=[`aria-label`],Jt=[`title`],Yt={class:`fc-foot`},Xt=[`title`],Zt=Se(z({__name:`FactorCard`,props:{factor:{},longOnly:{type:Boolean},hasSplit:{type:Boolean}},setup(e){let t=e,n=N(()=>Ae(t.factor,t.longOnly,t.hasSplit)),r=N(()=>n.value.filter(e=>e.state===`pass`).length),i=N(()=>{let e=t.factor;return t.longOnly?[{label:`IC均值`,...Q(`ic_mean`,e.ic_mean,Ve)},{label:`超额IR`,...Q(`excess_ir`,e.excess_ir,We)},{label:`OOS超额`,...Q(`oos_top_excess_return`,e.oos_top_excess_return,q)}]:[{label:`IC均值`,...Q(`ic_mean`,e.ic_mean,Ve)},{label:`IR`,...Q(`ir`,e.ir,Pe)},{label:`OOS多空`,...Q(`oos_long_short_return`,e.oos_long_short_return,q)}]}),a=N(()=>t.factor.passed?null:(t.factor.reasons??[]).find(e=>!Ie(e))??null);return(t,o)=>(W(),R(`button`,{type:`button`,class:I([`factor-card card card--hoverable`,e.factor.passed?`verdict-pass`:`verdict-fail`]),"data-testid":`verdict-card`},[F(`div`,Vt,[F(`span`,Ht,[F(`span`,Ut,Y(e.factor.factor_id),1),F(`span`,Wt,Y(e.factor.factor_name??``),1)]),e.factor.score!==null&&e.factor.score!==void 0?(W(),R(`span`,{key:0,class:I([`grade-badge`,Z(Ce)(e.factor.grade)]),"data-testid":`verdict-card-grade`},Y((e.factor.grade??`?`).toUpperCase())+` `+Y(e.factor.score.toFixed(0)),3)):(W(),R(`span`,Gt,`—`))]),F(`div`,Kt,[(W(!0),R(P,null,K(i.value,e=>(W(),R(`span`,{key:e.label,class:`fc-metric`},[F(`i`,null,Y(e.label),1),F(`b`,{class:I([`num`,e.cls])},Y(e.text),3)]))),128))]),F(`div`,{class:`fc-track`,"data-testid":`verdict-card-track`,"aria-label":`7 道闸门通过 ${r.value} 道`},[(W(!0),R(P,null,K(n.value,e=>(W(),R(`span`,{key:e.key,class:I([`gate-cell`,e.state]),title:e.detail},null,10,Jt))),128))],8,qt),F(`div`,Yt,[F(`span`,{class:I([`badge`,e.factor.passed?`pass`:`fail`])},Y(e.factor.passed?`PASS`:`FAIL`),3)]),a.value?(W(),R(`p`,{key:0,class:`fc-fail-reason`,title:a.value,"data-testid":`verdict-card-fail-reason`},Y(a.value),9,Xt)):O(``,!0)],2))}}),[[`__scopeId`,`data-v-b81fb106`]]),Qt={class:`vm-head`},$t={id:`vm-title`},en={class:`fid num`},tn={class:`fname`},nn={class:`vm-context t-muted`},rn={key:0,class:`vm-expr num`},an={class:`vm-metrics`},on={class:`vm-reasons`},sn={class:`vm-nav`},cn=[`disabled`],ln={class:`vm-pos num`},un=[`disabled`],dn=Se(z({__name:`FactorDetailModal`,props:{show:{type:Boolean},factors:{},index:{},longOnly:{type:Boolean},hasSplit:{type:Boolean},runTitle:{}},emits:[`update:show`,`navigate`],setup(e,{emit:t}){let n=e,r=t,i=N(()=>n.factors[n.index]??null),a={text:`—`,cls:``},o=N(()=>{let e=i.value;if(!e)return[];let t=(e,t,r)=>n.hasSplit?Q(e,t,r):a;return n.longOnly?[{label:`IC均值`,gloss:`ic`,is:Q(`ic_mean`,e.ic_mean,Ve),oos:t(`oos_ic_mean`,e.oos_ic_mean,Ve)},{label:`超额信息比`,gloss:`ir`,is:Q(`excess_ir`,e.excess_ir,We),oos:a},{label:`超额正率`,gloss:`ic_posrate`,is:Q(`excess_positive_rate`,e.excess_positive_rate,q),oos:a},{label:`单调性`,gloss:`monotonicity`,is:Q(`monotonicity_score`,e.monotonicity_score,We),oos:a},{label:`Top超额`,gloss:`ls_is`,is:Q(`top_excess_return`,e.top_excess_return,q),oos:t(`oos_top_excess_return`,e.oos_top_excess_return,q)}]:[{label:`IC均值`,gloss:`ic`,is:Q(`ic_mean`,e.ic_mean,Ve),oos:t(`oos_ic_mean`,e.oos_ic_mean,Ve)},{label:`IR`,gloss:`ir`,is:Q(`ir`,e.ir,Pe),oos:t(`oos_ir`,e.oos_ir,Pe)},{label:`IC正率`,gloss:`ic_posrate`,is:Q(`ic_positive_rate`,e.ic_positive_rate,q),oos:a},{label:`单调性`,gloss:`monotonicity`,is:Q(`monotonicity_score`,e.monotonicity_score,We),oos:a},{label:`多空收益`,gloss:`ls_is`,is:Q(`long_short_return`,e.long_short_return,q),oos:t(`oos_long_short_return`,e.oos_long_short_return,q)}]});function s(e){let t=n.index+e;t<0||t>=n.factors.length||r(`navigate`,t)}function c(e){e.key===`ArrowLeft`?(e.preventDefault(),s(-1)):e.key===`ArrowRight`&&(e.preventDefault(),s(1))}let l=U(null);return G(()=>n.show,e=>{e&&ve(()=>l.value?.focus())}),(t,n)=>(W(),Ze(Z(Lt),{show:e.show,"onUpdate:show":n[3]||=e=>r(`update:show`,e)},{default:H(()=>[i.value?(W(),R(`div`,{key:0,ref_key:`modalEl`,ref:l,class:`verdict-modal`,"data-testid":`verdict-modal`,role:`dialog`,"aria-modal":`true`,"aria-labelledby":`vm-title`,tabindex:`-1`,onKeydown:c},[F(`header`,Qt,[F(`h3`,$t,[F(`span`,en,Y(i.value.factor_id),1),F(`span`,tn,Y(i.value.factor_name??``),1)]),i.value.score!==null&&i.value.score!==void 0?(W(),R(`span`,{key:0,class:I([`grade-badge`,Z(Ce)(i.value.grade)])},Y((i.value.grade??`?`).toUpperCase())+` `+Y(i.value.score.toFixed(0)),3)):O(``,!0),L(b,{term:i.value.passed?`verdict_pass`:`verdict_fail`,plain:``},{default:H(()=>[F(`span`,{class:I([`badge`,i.value.passed?`pass`:`fail`])},Y(i.value.passed?`PASS`:`FAIL`),3)]),_:1},8,[`term`]),F(`button`,{type:`button`,class:`vm-close`,"aria-label":`关闭`,onClick:n[0]||=e=>r(`update:show`,!1)},`✕`)]),F(`p`,nn,Y(e.runTitle),1),i.value.expression?(W(),R(`code`,rn,Y(i.value.expression),1)):O(``,!0),n[8]||=F(`h4`,{class:`vm-section`},`指标对照`,-1),F(`table`,an,[n[4]||=F(`thead`,null,[F(`tr`,null,[F(`th`,{scope:`col`},[F(`span`,{class:`sr-only`},`指标`)]),F(`th`,{class:`th-num`,scope:`col`},`IS`),F(`th`,{class:`th-num`,scope:`col`},`OOS`)])],-1),F(`tbody`,null,[(W(!0),R(P,null,K(o.value,e=>(W(),R(`tr`,{key:e.label},[F(`td`,null,[L(b,{term:e.gloss},{default:H(()=>[A(Y(e.label),1)]),_:2},1032,[`term`])]),F(`td`,{class:I([`num`,e.is.cls])},Y(e.is.text),3),F(`td`,{class:I([`num`,e.oos.cls])},Y(e.oos.text),3)]))),128))])]),n[9]||=F(`h4`,{class:`vm-section`},`逐关判定`,-1),F(`ul`,on,[(W(!0),R(P,null,K(i.value.reasons??[],(e,t)=>(W(),R(`li`,{key:t,class:I(Z(Ie)(e)?`r-pass`:`r-fail`)},Y(e),3))),128))]),F(`footer`,sn,[F(`button`,{type:`button`,disabled:e.index===0,"data-testid":`verdict-modal-prev`,onClick:n[1]||=e=>s(-1)},[n[5]||=A(` ‹ 上一个`,-1),e.factors[e.index-1]?(W(),R(P,{key:0},[A(` (`+Y(e.factors[e.index-1].factor_id)+`)`,1)],64)):O(``,!0)],8,cn),F(`span`,ln,Y(e.index+1)+` / `+Y(e.factors.length),1),F(`button`,{type:`button`,disabled:e.index===e.factors.length-1,"data-testid":`verdict-modal-next`,onClick:n[2]||=e=>s(1)},[n[6]||=A(`下一个`,-1),e.factors[e.index+1]?(W(),R(P,{key:0},[A(` (`+Y(e.factors[e.index+1].factor_id)+`)`,1)],64)):O(``,!0),n[7]||=A(` ›`,-1)],8,un)])],544)):O(``,!0)]),_:1},8,[`show`]))}}),[[`__scopeId`,`data-v-1594a6c5`]]),fn={class:`card form-card`,open:``,"data-testid":`factor-test-form`},pn={class:`group-title`},mn={class:`fchips`},hn=[`title`,`onClick`],gn={class:`fchip-id`},_n={class:`fchip-name`},vn={class:`form-row`},yn={key:1,class:`t-warn hint`},bn={"data-testid":`ft-job-area`},xn=Se(z({__name:`FactorTestForm`,props:{lastSplitHint:{}},emits:[`refresh`],setup(e,{emit:t}){let n=e,r=t,i=U(``),a=U([]),o=U(new Set);async function s(){try{let e=await Te(`/api/meta/factors`),t=new Map(e.factors.map(e=>[e.factor_id,e]));a.value=Object.entries(e.groups).map(([e,n])=>({group:e,chips:n.filter(e=>t.has(e)).map(e=>({factor:t.get(e),disabled:t.get(e).field_ready===!1}))}));let n=a.value.find(e=>e.group===`P0`);o.value=new Set(n?.chips.filter(e=>!e.disabled).map(e=>e.factor.factor_id))}catch(e){i.value=e.message}}s();function c(e,t){if(t)return;let n=new Set(o.value);n.has(e)?n.delete(e):n.add(e),o.value=n}let l=U(null),u=U(null),f=U(null),p=U(`long_only`),m=U(5),h=U(5),g=U(.003),_=U([]),v=U(!1);G(()=>n.lastSplitHint,e=>{!f.value&&e&&(f.value=e)},{immediate:!0});let y=[{label:`Top层纯多头超额 (long_only)`,value:`long_only`},{label:`多空价差 (long_short)`,value:`long_short`}],C=N(()=>o.value.size>1&&!f.value);async function ee(){if(i.value=``,o.value.size===0){i.value=`至少勾选一个因子`;return}let e={factors:[...o.value].join(`,`),start_date:l.value??``,end_date:u.value??``,objective:p.value,num_layers:m.value,rebalance_days:h.value,cost_rate:g.value};f.value&&(e.split_date=f.value),v.value=!0;try{let t=await Ee(`/api/jobs/factor-test`,e);_.value.unshift(t.job_id)}catch(e){i.value=e.message}finally{v.value=!1}}return(e,t)=>(W(),R(`details`,fn,[t[21]||=F(`summary`,null,`因子检验`,-1),i.value?(W(),Ze(d,{key:0,msg:i.value},null,8,[`msg`])):O(``,!0),(W(!0),R(P,null,K(a.value,e=>(W(),R(`div`,{key:e.group,class:`factor-group`,"data-testid":`ft-factors`},[L(b,{term:`factor_group`},{default:H(()=>[F(`span`,pn,Y(e.group),1)]),_:2},1024),F(`div`,mn,[(W(!0),R(P,null,K(e.chips,e=>(W(),R(`button`,{key:e.factor.factor_id,type:`button`,class:I([`fchip`,{checked:o.value.has(e.factor.factor_id),disabled:e.disabled}]),title:(e.factor.expression??``)+(e.disabled?`（数据管道缺字段，禁用）`:``),"data-testid":`ft-factor-chip`,onClick:t=>c(e.factor.factor_id,e.disabled)},[F(`span`,gn,Y(e.factor.factor_id),1),F(`span`,_n,Y(e.factor.name),1)],10,hn))),128))])]))),128)),F(`div`,vn,[F(`label`,null,[t[8]||=A(`起始 `,-1),L(Z(x),{"formatted-value":l.value,"onUpdate:formattedValue":t[0]||=e=>l.value=e,"value-format":`yyyy-MM-dd`,type:`date`,clearable:``},null,8,[`formatted-value`])]),F(`label`,null,[t[9]||=A(`结束 `,-1),L(Z(x),{"formatted-value":u.value,"onUpdate:formattedValue":t[1]||=e=>u.value=e,"value-format":`yyyy-MM-dd`,type:`date`,clearable:``},null,8,[`formatted-value`])]),F(`label`,null,[L(b,{term:`split_date`},{default:H(()=>[...t[10]||=[A(`IS/OOS 切分`,-1)]]),_:1}),t[11]||=A(),L(Z(x),{"formatted-value":f.value,"onUpdate:formattedValue":t[2]||=e=>f.value=e,"value-format":`yyyy-MM-dd`,type:`date`,clearable:``},null,8,[`formatted-value`])]),F(`label`,null,[L(b,{term:`objective`},{default:H(()=>[...t[12]||=[A(`记分牌`,-1)]]),_:1}),t[13]||=A(),L(Z(T),{value:p.value,"onUpdate:value":t[3]||=e=>p.value=e,options:y,"aria-label":`记分牌口径`,style:{width:`220px`}},null,8,[`value`])]),F(`label`,null,[L(b,{term:`layers`},{default:H(()=>[...t[14]||=[A(`分层`,-1)]]),_:1}),t[15]||=A(),L(Z(E),{value:m.value,"onUpdate:value":t[4]||=e=>m.value=e,min:2,max:10,style:{width:`90px`}},null,8,[`value`])]),F(`label`,null,[L(b,{term:`rebalance`},{default:H(()=>[...t[16]||=[A(`调仓(日)`,-1)]]),_:1}),t[17]||=A(),L(Z(E),{value:h.value,"onUpdate:value":t[5]||=e=>h.value=e,min:1,style:{width:`90px`}},null,8,[`value`])]),F(`label`,null,[L(b,{term:`cost_rate`},{default:H(()=>[...t[18]||=[A(`成本率`,-1)]]),_:1}),t[19]||=A(),L(Z(E),{value:g.value,"onUpdate:value":t[6]||=e=>g.value=e,step:.001,style:{width:`110px`}},null,8,[`value`])]),L(Z(w),{type:`primary`,loading:v.value,disabled:v.value,"data-testid":`ft-submit`,onClick:ee},{default:H(()=>[...t[20]||=[A(`提交检验`,-1)]]),_:1},8,[`loading`,`disabled`])]),C.value?(W(),R(`p`,yn,` 多因子批量检验未设 IS/OOS 切分——存在多重检验风险，建议保留切分日期。 `)):O(``,!0),F(`div`,bn,[(W(!0),R(P,null,K(_.value,e=>(W(),Ze(S,{key:e,"job-id":e,onDone:t[7]||=()=>r(`refresh`)},null,8,[`job-id`]))),128))])]))}}),[[`__scopeId`,`data-v-6cf78fbb`]]);function Sn(e,t,n){if(n.length===0)return{selectedIdx:0,newRunId:null};let r=e?n.findIndex(t=>t.run_id===e):-1,i=r>=0?r:0,a=new Set(t),o=n[0];return{selectedIdx:i,newRunId:r>0&&o&&!a.has(o.run_id)?o.run_id:null}}function Cn(e){return e===`long_only`?`长多`:e===`long_short`?`多空`:`?`}function wn(e){let t=e.factors.length,n=Cn(e.params?.objective),r=e.params?.split;return{title:`${t} 因子 · ${n} · ${r?`切分 ${r}`:`未切分`}`,subtitle:`${(e.created_at??``).slice(5,16)} · ${e.run_id}`}}var Tn=[{label:`判决 + 评分`,value:`verdict`},{label:`评分`,value:`score`},{label:`IC 均值`,value:`ic`},{label:`样本外变现`,value:`oos_realize`},{label:`提交顺序`,value:`submitted`}];function $(e){return e??-1/0}function En(e,t){return $(t?e.oos_top_excess_return:e.oos_long_short_return)}function Dn(e,t,n){let r=[...e];switch(t){case`verdict`:return r.sort((e,t)=>Number(t.passed)-Number(e.passed)||$(t.score)-$(e.score));case`score`:return r.sort((e,t)=>$(t.score)-$(e.score));case`ic`:return r.sort((e,t)=>$(t.ic_mean)-$(e.ic_mean));case`oos_realize`:return r.sort((e,t)=>En(t,n)-En(e,n));case`submitted`:return r;default:return r}}function On(e,t){return t===`pass`?e.filter(e=>e.passed):t===`fail`?e.filter(e=>!e.passed):e}var kn={"data-testid":`page-verdicts`},An={key:1,class:`t-muted`},jn={key:2,class:`t-muted`,"data-testid":`verdicts-empty`},Mn={key:0,class:`new-run-notice`,role:`status`,"data-testid":`verdict-new-run-notice`},Nn={class:`result-head`},Pn={class:`confirm-body`},Fn={class:`filter-seg`,role:`group`,"aria-label":`按判决过滤`,"data-testid":`verdict-filter`},In=[`aria-pressed`],Ln=[`aria-pressed`],Rn=[`aria-pressed`],zn={class:`meta-strip card`},Bn={key:1},Vn={key:1,class:`t-muted`,"data-testid":`verdict-filter-empty`},Hn={key:2,class:`factor-grid`,"data-testid":`verdict-grid`},Un=Se(z({__name:`Verdicts`,setup(e){let t=U(``),n=U(!0),r=U([]),i=U(0),a=U(null);async function o(){let e=r.value[i.value]?.run_id??null,o=r.value.map(e=>e.run_id);try{let n=await Te(`/api/research/verdicts`);r.value=n.runs;let s=Sn(e,o,n.runs);i.value=s.selectedIdx,a.value=s.newRunId,t.value=``}catch(e){t.value=e.message}finally{n.value=!1}}function s(){let e=r.value.findIndex(e=>e.run_id===a.value);e>=0&&(i.value=e),a.value=null}o();let c=N(()=>r.value[i.value]??null),l=N(()=>c.value?.params?.objective===`long_only`),u=N(()=>!!c.value?.params?.split),f=N(()=>r.value[0]?.params?.split??null),m=U(!1);async function h(){let e=c.value?.run_id;if(e){m.value=!0;try{await qe(`/api/research/verdicts/${e}`),await o()}catch(e){t.value=e.message}finally{m.value=!1}}}let g=N(()=>r.value.map((e,t)=>({label:`${wn(e).title}（${(e.created_at??``).slice(5,16)} · ${e.run_id}）`,value:t}))),_=N(()=>{let e=c.value?.params??{};return[{label:`区间`,value:`${e.start??`?`} → ${e.end??`?`}`},{label:`切分`,value:e.split??`无`,gloss:`split_date`},{label:`调仓`,value:`${e.rebalance_days??1} 日`,gloss:`rebalance`},{label:`记分牌`,value:l.value?`长多(Top超额)`:`多空`,gloss:`objective`},{label:`覆盖股票池`,value:`${e.universe_count??`?`} 只`,gloss:`universe_lineage`},{label:`特征`,value:`v${e.feature_version??`?`}`}]}),v=U(`all`),y=U(`verdict`),x=N(()=>c.value?.factors.length??0),S=N(()=>c.value?.factors.filter(e=>e.passed).length??0),C=N(()=>x.value-S.value),E=N(()=>c.value?Dn(On(c.value.factors,v.value),y.value,l.value):[]),D=U(!1),te=U(0),k=U(null);function ne(e){k.value=document.activeElement,te.value=e,D.value=!0}return G(D,e=>{e||k.value?.focus()}),G(()=>c.value?.run_id,()=>{D.value=!1}),G([v,y],()=>{D.value=!1}),G(i,e=>{e===0&&(a.value=null)}),(e,k)=>(W(),R(`section`,kn,[L(p,{title:`因子判决`},{default:H(()=>[...k[9]||=[A(` 先检验因子，判决结果随后以卡片呈现——左缘色条与闸门轨道标出 PASS/FAIL，点击卡片看全部细节。 `,-1)]]),_:1}),t.value?(W(),Ze(d,{key:0,msg:t.value},null,8,[`msg`])):O(``,!0),L(xn,{"last-split-hint":f.value,onRefresh:o},null,8,[`last-split-hint`]),n.value?(W(),R(`p`,An,`加载判决轮次…`)):r.value.length?O(``,!0):(W(),R(`p`,jn,` 暂无判决轮次 — 用上方表单提交一次因子检验。 `)),c.value?(W(),R(P,{key:3},[a.value?(W(),R(`div`,Mn,[k[10]||=F(`span`,null,`已有更新的判决轮就绪 — 当前仍停在你正在查看的这轮。`,-1),F(`button`,{type:`button`,class:`notice-view`,onClick:s},`查看最新`),F(`button`,{type:`button`,class:`notice-dismiss`,"aria-label":`忽略新轮提示`,onClick:k[0]||=e=>a.value=null},`✕`)])):O(``,!0),F(`div`,Nn,[k[14]||=F(`span`,{class:`list-title`},`判决结果`,-1),L(Z(T),{value:i.value,"onUpdate:value":k[1]||=e=>i.value=e,options:g.value,size:`small`,style:{width:`380px`},"aria-label":`判决轮次`,"data-testid":`run-select`},null,8,[`value`,`options`]),L(Z(ee),{"positive-text":`删除`,"negative-text":`取消`,onPositiveClick:h},{trigger:H(()=>[L(Z(w),{size:`small`,quaternary:``,loading:m.value,"data-testid":`verdict-delete`},{default:H(()=>[...k[11]||=[A(`删除本轮`,-1)]]),_:1},8,[`loading`])]),default:H(()=>[F(`div`,Pn,[k[12]||=F(`div`,null,`删除这轮判决？`,-1),F(`div`,null,[F(`b`,null,Y(g.value[i.value]?.label),1)]),k[13]||=F(`div`,{class:`t-muted`},`不可恢复`,-1)])]),_:1}),F(`div`,Fn,[F(`button`,{type:`button`,class:I({active:v.value===`all`}),"aria-pressed":v.value===`all`,onClick:k[2]||=e=>v.value=`all`},`全部 `+Y(x.value),11,In),F(`button`,{type:`button`,class:I({active:v.value===`pass`}),"aria-pressed":v.value===`pass`,onClick:k[3]||=e=>v.value=`pass`},`PASS `+Y(S.value),11,Ln),F(`button`,{type:`button`,class:I({active:v.value===`fail`}),"aria-pressed":v.value===`fail`,onClick:k[4]||=e=>v.value=`fail`},`FAIL `+Y(C.value),11,Rn)]),L(Z(T),{value:y.value,"onUpdate:value":k[5]||=e=>y.value=e,options:Z(Tn),size:`small`,style:{width:`190px`},"aria-label":`因子排序`,"data-testid":`verdict-sort`},null,8,[`value`,`options`])]),F(`div`,zn,[(W(!0),R(P,null,K(_.value,e=>(W(),R(`span`,{key:e.label,class:`rm`},[e.gloss?(W(),Ze(b,{key:0,term:e.gloss},{default:H(()=>[F(`i`,null,Y(e.label),1)]),_:2},1032,[`term`])):(W(),R(`i`,Bn,Y(e.label),1)),F(`b`,null,Y(e.value),1)]))),128))]),E.value.length?(W(),R(`div`,Hn,[(W(!0),R(P,null,K(E.value,(e,t)=>(W(),Ze(Zt,{key:e.factor_id,factor:e,"long-only":l.value,"has-split":u.value,onClick:e=>ne(t)},null,8,[`factor`,`long-only`,`has-split`,`onClick`]))),128))])):(W(),R(`p`,Vn,[k[15]||=A(` 无匹配因子 — `,-1),F(`button`,{type:`button`,class:`link-btn`,onClick:k[6]||=e=>v.value=`all`},`清除过滤`)]))],64)):O(``,!0),L(dn,{show:D.value,"onUpdate:show":k[7]||=e=>D.value=e,factors:E.value,index:te.value,"long-only":l.value,"has-split":u.value,"run-title":c.value?Z(wn)(c.value).title:``,onNavigate:k[8]||=e=>te.value=e},null,8,[`show`,`factors`,`index`,`long-only`,`has-split`,`run-title`])]))}}),[[`__scopeId`,`data-v-f10a515d`]]);export{Un as default};
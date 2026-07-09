import{E as e,F as t,G as n,I as r,K as i,L as a,M as o,O as s,P as c,Q as l,S as u,T as d,U as f,W as p,Z as m,_ as h,et as g,f as _,j as v,k as y,l as b,o as x,p as S,v as C,w,y as T}from"./PageHeader-ao-gakQg.js";import{c as ee,d as E,f as D,i as O,n as k,o as te,p as A,r as j,s as M}from"./usePolling-LpjtPFBT.js";import{n as ne,s as re}from"./GlossaryTip-DCxzBhfi.js";import{$t as N,A as P,Cn as F,D as ie,Dt as I,En as ae,Et as oe,Ft as L,In as R,It as z,Kt as B,Lt as V,M as H,Mt as U,Nn as W,Nt as G,O as se,On as ce,Ot as K,Rt as q,T as le,Tn as ue,Tt as de,Wt as J,Yt as Y,_n as fe,cn as X,fn as pe,hn as me,in as he,ln as ge,on as Z,w as _e,xn as ve,xt as ye,y as be}from"./index-BM6owX4h.js";var Q=`v-hidden`,xe=v(`[v-hidden]`,{display:`none!important`}),Se=Z({name:`Overflow`,props:{getCounter:Function,getTail:Function,updateCounter:Function,onUpdateCount:Function,onUpdateOverflow:Function},setup(e,{slots:t}){let n=W(null),r=W(null);function i(i){let{value:a}=n,{getCounter:o,getTail:s}=e,c;if(c=o===void 0?r.value:o(),!a||!c)return;c.hasAttribute(Q)&&c.removeAttribute(Q);let{children:l}=a;if(i.showAllItemsBeforeCalculate)for(let e of l)e.hasAttribute(Q)&&e.removeAttribute(Q);let u=a.offsetWidth,d=[],f=t.tail?s?.():null,p=f?f.offsetWidth:0,m=!1,h=a.children.length-+!!t.tail;for(let t=0;t<h-1;++t){if(t<0)continue;let n=l[t];if(m){n.hasAttribute(Q)||n.setAttribute(Q,``);continue}else n.hasAttribute(Q)&&n.removeAttribute(Q);let r=n.offsetWidth;if(p+=r,d[t]=r,p>u){let{updateCounter:n}=e;for(let r=t;r>=0;--r){let i=h-1-r;n===void 0?c.textContent=`${i}`:n(i);let a=c.offsetWidth;if(p-=d[r],p+a<=u||r===0){m=!0,t=r-1,f&&(t===-1?(f.style.maxWidth=`${u-a}px`,f.style.boxSizing=`border-box`):f.style.maxWidth=``);let{onUpdateCount:n}=e;n&&n(i);break}}}}let{onUpdateOverflow:g}=e;m?g!==void 0&&g(!0):(g!==void 0&&g(!1),c.setAttribute(Q,``))}let a=de();return xe.mount({id:`vueuc/overflow`,head:!0,anchorMetaName:o,ssr:a}),fe(()=>i({showAllItemsBeforeCalculate:!1})),{selfRef:n,counterRef:r,sync:i}},render(){let{$slots:e}=this;return pe(()=>this.sync({showAllItemsBeforeCalculate:!1})),X(`div`,{class:`v-overflow`,ref:`selfRef`},[F(e,`default`),e.counter?e.counter():X(`span`,{style:{display:`inline-block`},ref:`counterRef`}),e.tail?e.tail():null])}});function Ce(e,t){t&&(fe(()=>{let{value:n}=e;n&&s.registerHandler(n,t)}),ue(e,(e,t)=>{t&&s.unregisterHandler(t)},{deep:!1}),me(()=>{let{value:t}=e;t&&s.unregisterHandler(t)}))}function we(e){switch(typeof e){case`string`:return e||void 0;case`number`:return String(e);default:return}}function Te(e){let t=e.filter(e=>e!==void 0);if(t.length!==0)return t.length===1?t[0]:t=>{e.forEach(e=>{e&&e(t)})}}function $(e,...t){return typeof e==`function`?e(...t):typeof e==`string`?he(e):typeof e==`number`?he(String(e)):null}var Ee=Z({name:`Checkmark`,render(){return X(`svg`,{xmlns:`http://www.w3.org/2000/svg`,viewBox:`0 0 16 16`},X(`g`,{fill:`none`},X(`path`,{d:`M14.046 3.486a.75.75 0 0 1-.032 1.06l-7.93 7.474a.85.85 0 0 1-1.188-.022l-2.68-2.72a.75.75 0 1 1 1.068-1.053l2.234 2.267l7.468-7.038a.75.75 0 0 1 1.06.032z`,fill:`currentColor`})))}}),De=te(`close`,()=>X(`svg`,{viewBox:`0 0 12 12`,version:`1.1`,xmlns:`http://www.w3.org/2000/svg`,"aria-hidden":!0},X(`g`,{stroke:`none`,"stroke-width":`1`,fill:`none`,"fill-rule":`evenodd`},X(`g`,{fill:`currentColor`,"fill-rule":`nonzero`},X(`path`,{d:`M2.08859116,2.2156945 L2.14644661,2.14644661 C2.32001296,1.97288026 2.58943736,1.95359511 2.7843055,2.08859116 L2.85355339,2.14644661 L6,5.293 L9.14644661,2.14644661 C9.34170876,1.95118446 9.65829124,1.95118446 9.85355339,2.14644661 C10.0488155,2.34170876 10.0488155,2.65829124 9.85355339,2.85355339 L6.707,6 L9.85355339,9.14644661 C10.0271197,9.32001296 10.0464049,9.58943736 9.91140884,9.7843055 L9.85355339,9.85355339 C9.67998704,10.0271197 9.41056264,10.0464049 9.2156945,9.91140884 L9.14644661,9.85355339 L6,6.707 L2.85355339,9.85355339 C2.65829124,10.0488155 2.34170876,10.0488155 2.14644661,9.85355339 C1.95118446,9.65829124 1.95118446,9.34170876 2.14644661,9.14644661 L5.293,6 L2.14644661,2.85355339 C1.97288026,2.67998704 1.95359511,2.41056264 2.08859116,2.2156945 L2.14644661,2.14644661 L2.08859116,2.2156945 Z`}))))),Oe=Z({name:`Empty`,render(){return X(`svg`,{viewBox:`0 0 28 28`,fill:`none`,xmlns:`http://www.w3.org/2000/svg`},X(`path`,{d:`M26 7.5C26 11.0899 23.0899 14 19.5 14C15.9101 14 13 11.0899 13 7.5C13 3.91015 15.9101 1 19.5 1C23.0899 1 26 3.91015 26 7.5ZM16.8536 4.14645C16.6583 3.95118 16.3417 3.95118 16.1464 4.14645C15.9512 4.34171 15.9512 4.65829 16.1464 4.85355L18.7929 7.5L16.1464 10.1464C15.9512 10.3417 15.9512 10.6583 16.1464 10.8536C16.3417 11.0488 16.6583 11.0488 16.8536 10.8536L19.5 8.20711L22.1464 10.8536C22.3417 11.0488 22.6583 11.0488 22.8536 10.8536C23.0488 10.6583 23.0488 10.3417 22.8536 10.1464L20.2071 7.5L22.8536 4.85355C23.0488 4.65829 23.0488 4.34171 22.8536 4.14645C22.6583 3.95118 22.3417 3.95118 22.1464 4.14645L19.5 6.79289L16.8536 4.14645Z`,fill:`currentColor`}),X(`path`,{d:`M25 22.75V12.5991C24.5572 13.0765 24.053 13.4961 23.5 13.8454V16H17.5L17.3982 16.0068C17.0322 16.0565 16.75 16.3703 16.75 16.75C16.75 18.2688 15.5188 19.5 14 19.5C12.4812 19.5 11.25 18.2688 11.25 16.75L11.2432 16.6482C11.1935 16.2822 10.8797 16 10.5 16H4.5V7.25C4.5 6.2835 5.2835 5.5 6.25 5.5H12.2696C12.4146 4.97463 12.6153 4.47237 12.865 4H6.25C4.45507 4 3 5.45507 3 7.25V22.75C3 24.5449 4.45507 26 6.25 26H21.75C23.5449 26 25 24.5449 25 22.75ZM4.5 22.75V17.5H9.81597L9.85751 17.7041C10.2905 19.5919 11.9808 21 14 21L14.215 20.9947C16.2095 20.8953 17.842 19.4209 18.184 17.5H23.5V22.75C23.5 23.7165 22.7165 24.5 21.75 24.5H6.25C5.2835 24.5 4.5 23.7165 4.5 22.75Z`,fill:`currentColor`}))}}),ke=G(`base-close`,`
 display: flex;
 align-items: center;
 justify-content: center;
 cursor: pointer;
 background-color: transparent;
 color: var(--n-close-icon-color);
 border-radius: var(--n-close-border-radius);
 height: var(--n-close-size);
 width: var(--n-close-size);
 font-size: var(--n-close-icon-size);
 outline: none;
 border: none;
 position: relative;
 padding: 0;
`,[z(`absolute`,`
 height: var(--n-close-icon-size);
 width: var(--n-close-icon-size);
 `),U(`&::before`,`
 content: "";
 position: absolute;
 width: var(--n-close-size);
 height: var(--n-close-size);
 left: 50%;
 top: 50%;
 transform: translateY(-50%) translateX(-50%);
 transition: inherit;
 border-radius: inherit;
 `),V(`disabled`,[U(`&:hover`,`
 color: var(--n-close-icon-color-hover);
 `),U(`&:hover::before`,`
 background-color: var(--n-close-color-hover);
 `),U(`&:focus::before`,`
 background-color: var(--n-close-color-hover);
 `),U(`&:active`,`
 color: var(--n-close-icon-color-pressed);
 `),U(`&:active::before`,`
 background-color: var(--n-close-color-pressed);
 `)]),z(`disabled`,`
 cursor: not-allowed;
 color: var(--n-close-icon-color-disabled);
 background-color: transparent;
 `),z(`round`,[U(`&::before`,`
 border-radius: 50%;
 `)])]),Ae=Z({name:`BaseClose`,props:{isButtonTag:{type:Boolean,default:!0},clsPrefix:{type:String,required:!0},disabled:{type:Boolean,default:void 0},focusable:{type:Boolean,default:!0},round:Boolean,onClick:Function,absolute:Boolean},setup(e){return _(`-base-close`,ke,R(e,`clsPrefix`)),()=>{let{clsPrefix:t,disabled:n,absolute:r,round:i,isButtonTag:a}=e;return X(a?`button`:`div`,{type:a?`button`:void 0,tabindex:n||!e.focusable?-1:0,"aria-disabled":n,"aria-label":`close`,role:a?void 0:`button`,disabled:n,class:[`${t}-base-close`,r&&`${t}-base-close--absolute`,n&&`${t}-base-close--disabled`,i&&`${t}-base-close--round`],onMousedown:t=>{e.focusable||t.preventDefault()},onClick:e.onClick},X(M,{clsPrefix:t},{default:()=>X(De,null)}))}}});function je(e){return Array.isArray(e)?e:[e]}var Me={STOP:`STOP`};function Ne(e,t){let n=t(e);e.children!==void 0&&n!==Me.STOP&&e.children.forEach(e=>Ne(e,t))}function Pe(e,t={}){let{preserveGroup:n=!1}=t,r=[],i=n?e=>{e.isLeaf||(r.push(e.key),a(e.children))}:e=>{e.isLeaf||(e.isGroup||r.push(e.key),a(e.children))};function a(e){e.forEach(i)}return a(e),r}function Fe(e,t){let{isLeaf:n}=e;return n===void 0?!t(e):n}function Ie(e){return e.children}function Le(e){return e.key}function Re(){return!1}function ze(e,t){let{isLeaf:n}=e;return!(n===!1&&!Array.isArray(t(e)))}function Be(e){return e.disabled===!0}function Ve(e,t){return e.isLeaf===!1&&!Array.isArray(t(e))}function He(e){return e==null?[]:Array.isArray(e)?e:e.checkedKeys??[]}function Ue(e){return e==null||Array.isArray(e)?[]:e.indeterminateKeys??[]}function We(e,t){let n=new Set(e);return t.forEach(e=>{n.has(e)||n.add(e)}),Array.from(n)}function Ge(e,t){let n=new Set(e);return t.forEach(e=>{n.has(e)&&n.delete(e)}),Array.from(n)}function Ke(e){return e?.type===`group`}function qe(e){let t=new Map;return e.forEach((e,n)=>{t.set(e.key,n)}),e=>t.get(e)??null}var Je=class extends Error{constructor(){super(),this.message=`SubtreeNotLoadedError: checking a subtree whose required nodes are not fully loaded.`}};function Ye(e,t,n,r){return $e(t.concat(e),n,r,!1)}function Xe(e,t){let n=new Set;return e.forEach(e=>{let r=t.treeNodeMap.get(e);if(r!==void 0){let e=r.parent;for(;e!==null&&!(e.disabled||n.has(e.key));)n.add(e.key),e=e.parent}}),n}function Ze(e,t,n,r){let i=$e(t,n,r,!1),a=$e(e,n,r,!0),o=Xe(e,n),s=[];return i.forEach(e=>{(a.has(e)||o.has(e))&&s.push(e)}),s.forEach(e=>i.delete(e)),i}function Qe(e,t){let{checkedKeys:n,keysToCheck:r,keysToUncheck:i,indeterminateKeys:a,cascade:o,leafOnly:s,checkStrategy:c,allowNotLoaded:l}=e;if(!o)return r===void 0?i===void 0?{checkedKeys:Array.from(n),indeterminateKeys:Array.from(a)}:{checkedKeys:Ge(n,i),indeterminateKeys:Array.from(a)}:{checkedKeys:We(n,r),indeterminateKeys:Array.from(a)};let{levelTreeNodeMap:u}=t,d;d=i===void 0?r===void 0?$e(n,t,l,!1):Ye(r,n,t,l):Ze(i,n,t,l);let f=c===`parent`,p=c===`child`||s,m=d,h=new Set,g=Math.max.apply(null,Array.from(u.keys()));for(let e=g;e>=0;--e){let t=e===0,n=u.get(e);for(let e of n){if(e.isLeaf)continue;let{key:n,shallowLoaded:r}=e;if(p&&r&&e.children.forEach(e=>{!e.disabled&&!e.isLeaf&&e.shallowLoaded&&m.has(e.key)&&m.delete(e.key)}),e.disabled||!r)continue;let i=!0,a=!1,o=!0;for(let t of e.children){let e=t.key;if(!t.disabled){if(o&&=!1,m.has(e))a=!0;else if(h.has(e)){a=!0,i=!1;break}else if(i=!1,a)break}}i&&!o?(f&&e.children.forEach(e=>{!e.disabled&&m.has(e.key)&&m.delete(e.key)}),m.add(n)):a&&h.add(n),t&&p&&m.has(n)&&m.delete(n)}}return{checkedKeys:Array.from(m),indeterminateKeys:Array.from(h)}}function $e(e,t,n,r){let{treeNodeMap:i,getChildren:a}=t,o=new Set,s=new Set(e);return e.forEach(e=>{let t=i.get(e);t!==void 0&&Ne(t,e=>{if(e.disabled)return Me.STOP;let{key:t}=e;if(!o.has(t)&&(o.add(t),s.add(t),Ve(e.rawNode,a))){if(r)return Me.STOP;if(!n)throw new Je}})}),s}function et(e,{includeGroup:t=!1,includeSelf:n=!0},r){let i=r.treeNodeMap,a=e==null?null:i.get(e)??null,o={keyPath:[],treeNodePath:[],treeNode:a};if(a?.ignored)return o.treeNode=null,o;for(;a;)!a.ignored&&(t||!a.isGroup)&&o.treeNodePath.push(a),a=a.parent;return o.treeNodePath.reverse(),n||o.treeNodePath.pop(),o.keyPath=o.treeNodePath.map(e=>e.key),o}function tt(e){if(e.length===0)return null;let t=e[0];return t.isGroup||t.ignored||t.disabled?t.getNext():t}function nt(e,t){let n=e.siblings,r=n.length,{index:i}=e;return t?n[(i+1)%r]:i===n.length-1?null:n[i+1]}function rt(e,t,{loop:n=!1,includeDisabled:r=!1}={}){let i=t===`prev`?it:nt,a={reverse:t===`prev`},o=!1,s=null;function c(t){if(t!==null){if(t===e){if(!o)o=!0;else if(!e.disabled&&!e.isGroup){s=e;return}}else if((!t.disabled||r)&&!t.ignored&&!t.isGroup){s=t;return}if(t.isGroup){let e=ot(t,a);e===null?c(i(t,n)):s=e}else{let e=i(t,!1);if(e!==null)c(e);else{let e=at(t);e?.isGroup?c(i(e,n)):n&&c(i(t,!0))}}}}return c(e),s}function it(e,t){let n=e.siblings,r=n.length,{index:i}=e;return t?n[(i-1+r)%r]:i===0?null:n[i-1]}function at(e){return e.parent}function ot(e,t={}){let{reverse:n=!1}=t,{children:r}=e;if(r){let{length:e}=r,i=n?e-1:0,a=n?-1:e,o=n?-1:1;for(let e=i;e!==a;e+=o){let n=r[e];if(!n.disabled&&!n.ignored)if(n.isGroup){let e=ot(n,t);if(e!==null)return e}else return n}}return null}var st={getChild(){return this.ignored?null:ot(this)},getParent(){let{parent:e}=this;return e?.isGroup?e.getParent():e},getNext(e={}){return rt(this,`next`,e)},getPrev(e={}){return rt(this,`prev`,e)}};function ct(e,t){let n=t?new Set(t):void 0,r=[];function i(e){e.forEach(e=>{r.push(e),!(e.isLeaf||!e.children||e.ignored)&&(e.isGroup||n===void 0||n.has(e.key))&&i(e.children)})}return i(e),r}function lt(e,t){let n=e.key;for(;t;){if(t.key===n)return!0;t=t.parent}return!1}function ut(e,t,n,r,i,a=null,o=0){let s=[];return e.forEach((c,l)=>{var u;let d=Object.create(r);if(d.rawNode=c,d.siblings=s,d.level=o,d.index=l,d.isFirstChild=l===0,d.isLastChild=l+1===e.length,d.parent=a,!d.ignored){let e=i(c);Array.isArray(e)&&(d.children=ut(e,t,n,r,i,d,o+1))}s.push(d),t.set(d.key,d),n.has(o)||n.set(o,[]),(u=n.get(o))==null||u.push(d)}),s}function dt(e,t={}){let n=new Map,r=new Map,{getDisabled:i=Be,getIgnored:a=Re,getIsGroup:o=Ke,getKey:s=Le}=t,c=t.getChildren??Ie,l=t.ignoreEmptyChildren?e=>{let t=c(e);return Array.isArray(t)?t.length?t:null:t}:c,u=ut(e,n,r,Object.assign({get key(){return s(this.rawNode)},get disabled(){return i(this.rawNode)},get isGroup(){return o(this.rawNode)},get isLeaf(){return Fe(this.rawNode,l)},get shallowLoaded(){return ze(this.rawNode,l)},get ignored(){return a(this.rawNode)},contains(e){return lt(this,e)}},st),l);function d(e){if(e==null)return null;let t=n.get(e);return t&&!t.isGroup&&!t.ignored?t:null}function f(e){if(e==null)return null;let t=n.get(e);return t&&!t.ignored?t:null}function p(e,t){let n=f(e);return n?n.getPrev(t):null}function m(e,t){let n=f(e);return n?n.getNext(t):null}function h(e){let t=f(e);return t?t.getParent():null}function g(e){let t=f(e);return t?t.getChild():null}let _={treeNodes:u,treeNodeMap:n,levelTreeNodeMap:r,maxLevel:Math.max(...r.keys()),getChildren:l,getFlattenedNodes(e){return ct(u,e)},getNode:d,getPrev:p,getNext:m,getParent:h,getChild:g,getFirstAvailableNode(){return tt(u)},getPath(e,t={}){return et(e,t,_)},getCheckedKeys(e,t={}){let{cascade:n=!0,leafOnly:r=!1,checkStrategy:i=`all`,allowNotLoaded:a=!1}=t;return Qe({checkedKeys:He(e),indeterminateKeys:Ue(e),cascade:n,leafOnly:r,checkStrategy:i,allowNotLoaded:a},_)},check(e,t,n={}){let{cascade:r=!0,leafOnly:i=!1,checkStrategy:a=`all`,allowNotLoaded:o=!1}=n;return Qe({checkedKeys:He(t),indeterminateKeys:Ue(t),keysToCheck:e==null?[]:je(e),cascade:r,leafOnly:i,checkStrategy:a,allowNotLoaded:o},_)},uncheck(e,t,n={}){let{cascade:r=!0,leafOnly:i=!1,checkStrategy:a=`all`,allowNotLoaded:o=!1}=n;return Qe({checkedKeys:He(t),indeterminateKeys:Ue(t),keysToUncheck:e==null?[]:je(e),cascade:r,leafOnly:i,checkStrategy:a,allowNotLoaded:o},_)},getNonLeafKeys(e={}){return Pe(u,e)}};return _}var ft=G(`empty`,`
 display: flex;
 flex-direction: column;
 align-items: center;
 font-size: var(--n-font-size);
`,[L(`icon`,`
 width: var(--n-icon-size);
 height: var(--n-icon-size);
 font-size: var(--n-icon-size);
 line-height: var(--n-icon-size);
 color: var(--n-icon-color);
 transition:
 color .3s var(--n-bezier);
 `,[U(`+`,[L(`description`,`
 margin-top: 8px;
 `)])]),L(`description`,`
 transition: color .3s var(--n-bezier);
 color: var(--n-text-color);
 `),L(`extra`,`
 text-align: center;
 transition: color .3s var(--n-bezier);
 margin-top: 12px;
 color: var(--n-extra-text-color);
 `)]),pt=Z({name:`Empty`,props:Object.assign(Object.assign({},H.props),{description:String,showDescription:{type:Boolean,default:!0},showIcon:{type:Boolean,default:!0},size:{type:String,default:`medium`},renderIcon:Function}),slots:Object,setup(e){let{mergedClsPrefixRef:t,inlineThemeDisabled:n,mergedComponentPropsRef:r}=ye(e),i=H(`Empty`,`-empty`,ft,se,e,t),{localeRef:a}=ee(`Empty`),o=N(()=>e.description??r?.value?.Empty?.description),s=N(()=>r?.value?.Empty?.renderIcon||(()=>X(Oe,null))),c=N(()=>{let{size:t}=e,{common:{cubicBezierEaseInOut:n},self:{[q(`iconSize`,t)]:r,[q(`fontSize`,t)]:a,textColor:o,iconColor:s,extraTextColor:c}}=i.value;return{"--n-icon-size":r,"--n-font-size":a,"--n-bezier":n,"--n-text-color":o,"--n-icon-color":s,"--n-extra-text-color":c}}),l=n?C(`empty`,N(()=>{let t=``,{size:n}=e;return t+=n[0],t}),c,e):void 0;return{mergedClsPrefix:t,mergedRenderIcon:s,localizedDescription:N(()=>o.value||a.value.description),cssVars:n?void 0:c,themeClass:l?.themeClass,onRender:l?.onRender}},render(){let{$slots:e,mergedClsPrefix:t,onRender:n}=this;return n?.(),X(`div`,{class:[`${t}-empty`,this.themeClass],style:this.cssVars},this.showIcon?X(`div`,{class:`${t}-empty__icon`},e.icon?e.icon():X(M,{clsPrefix:t},{default:this.mergedRenderIcon})):null,this.showDescription?X(`div`,{class:`${t}-empty__description`},e.default?e.default():this.localizedDescription):null,e.extra?X(`div`,{class:`${t}-empty__extra`},e.extra()):null)}}),mt=Z({name:`NBaseSelectGroupHeader`,props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(){let{renderLabelRef:e,renderOptionRef:t,labelFieldRef:n,nodePropsRef:r}=ge(p);return{labelField:n,nodeProps:r,renderLabel:e,renderOption:t}},render(){let{clsPrefix:e,renderLabel:t,renderOption:n,nodeProps:r,tmNode:{rawNode:i}}=this,a=r?.(i),o=t?t(i,!1):$(i[this.labelField],i,!1),s=X(`div`,Object.assign({},a,{class:[`${e}-base-select-group-header`,a?.class]}),o);return i.render?i.render({node:s,option:i}):n?n({node:s,option:i,selected:!1}):s}});function ht(e,t){return X(J,{name:`fade-in-scale-up-transition`},{default:()=>e?X(M,{clsPrefix:t,class:`${t}-base-select-option__check`},{default:()=>X(Ee)}):null})}var gt=Z({name:`NBaseSelectOption`,props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(e){let{valueRef:t,pendingTmNodeRef:n,multipleRef:r,valueSetRef:i,renderLabelRef:a,renderOptionRef:o,labelFieldRef:s,valueFieldRef:c,showCheckmarkRef:l,nodePropsRef:u,handleOptionClick:d,handleOptionMouseEnter:f}=ge(p),m=I(()=>{let{value:t}=n;return t?e.tmNode.key===t.key:!1});function h(t){let{tmNode:n}=e;n.disabled||d(t,n)}function g(t){let{tmNode:n}=e;n.disabled||f(t,n)}function _(t){let{tmNode:n}=e,{value:r}=m;n.disabled||r||f(t,n)}return{multiple:r,isGrouped:I(()=>{let{tmNode:t}=e,{parent:n}=t;return n&&n.rawNode.type===`group`}),showCheckmark:l,nodeProps:u,isPending:m,isSelected:I(()=>{let{value:n}=t,{value:a}=r;if(n===null)return!1;let o=e.tmNode.rawNode[c.value];if(a){let{value:e}=i;return e.has(o)}else return n===o}),labelField:s,renderLabel:a,renderOption:o,handleMouseMove:_,handleMouseEnter:g,handleClick:h}},render(){let{clsPrefix:e,tmNode:{rawNode:t},isSelected:n,isPending:r,isGrouped:i,showCheckmark:a,nodeProps:o,renderOption:s,renderLabel:c,handleClick:l,handleMouseEnter:u,handleMouseMove:d}=this,f=ht(n,e),p=c?[c(t,n),a&&f]:[$(t[this.labelField],t,n),a&&f],m=o?.(t),h=X(`div`,Object.assign({},m,{class:[`${e}-base-select-option`,t.class,m?.class,{[`${e}-base-select-option--disabled`]:t.disabled,[`${e}-base-select-option--selected`]:n,[`${e}-base-select-option--grouped`]:i,[`${e}-base-select-option--pending`]:r,[`${e}-base-select-option--show-checkmark`]:a}],style:[m?.style||``,t.style||``],onClick:Te([l,m?.onClick]),onMouseenter:Te([u,m?.onMouseenter]),onMousemove:Te([d,m?.onMousemove])}),X(`div`,{class:`${e}-base-select-option__content`},p));return t.render?t.render({node:h,option:t,selected:n}):s?s({node:h,option:t,selected:n}):h}}),_t=G(`base-select-menu`,`
 line-height: 1.5;
 outline: none;
 z-index: 0;
 position: relative;
 border-radius: var(--n-border-radius);
 transition:
 background-color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier);
 background-color: var(--n-color);
`,[G(`scrollbar`,`
 max-height: var(--n-height);
 `),G(`virtual-list`,`
 max-height: var(--n-height);
 `),G(`base-select-option`,`
 min-height: var(--n-option-height);
 font-size: var(--n-option-font-size);
 display: flex;
 align-items: center;
 `,[L(`content`,`
 z-index: 1;
 white-space: nowrap;
 text-overflow: ellipsis;
 overflow: hidden;
 `)]),G(`base-select-group-header`,`
 min-height: var(--n-option-height);
 font-size: .93em;
 display: flex;
 align-items: center;
 `),G(`base-select-menu-option-wrapper`,`
 position: relative;
 width: 100%;
 `),L(`loading, empty`,`
 display: flex;
 padding: 12px 32px;
 flex: 1;
 justify-content: center;
 `),L(`loading`,`
 color: var(--n-loading-color);
 font-size: var(--n-loading-size);
 `),L(`header`,`
 padding: 8px var(--n-option-padding-left);
 font-size: var(--n-option-font-size);
 transition: 
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 border-bottom: 1px solid var(--n-action-divider-color);
 color: var(--n-action-text-color);
 `),L(`action`,`
 padding: 8px var(--n-option-padding-left);
 font-size: var(--n-option-font-size);
 transition: 
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 border-top: 1px solid var(--n-action-divider-color);
 color: var(--n-action-text-color);
 `),G(`base-select-group-header`,`
 position: relative;
 cursor: default;
 padding: var(--n-option-padding);
 color: var(--n-group-header-text-color);
 `),G(`base-select-option`,`
 cursor: pointer;
 position: relative;
 padding: var(--n-option-padding);
 transition:
 color .3s var(--n-bezier),
 opacity .3s var(--n-bezier);
 box-sizing: border-box;
 color: var(--n-option-text-color);
 opacity: 1;
 `,[z(`show-checkmark`,`
 padding-right: calc(var(--n-option-padding-right) + 20px);
 `),U(`&::before`,`
 content: "";
 position: absolute;
 left: 4px;
 right: 4px;
 top: 0;
 bottom: 0;
 border-radius: var(--n-border-radius);
 transition: background-color .3s var(--n-bezier);
 `),U(`&:active`,`
 color: var(--n-option-text-color-pressed);
 `),z(`grouped`,`
 padding-left: calc(var(--n-option-padding-left) * 1.5);
 `),z(`pending`,[U(`&::before`,`
 background-color: var(--n-option-color-pending);
 `)]),z(`selected`,`
 color: var(--n-option-text-color-active);
 `,[U(`&::before`,`
 background-color: var(--n-option-color-active);
 `),z(`pending`,[U(`&::before`,`
 background-color: var(--n-option-color-active-pending);
 `)])]),z(`disabled`,`
 cursor: not-allowed;
 `,[V(`selected`,`
 color: var(--n-option-text-color-disabled);
 `),z(`selected`,`
 opacity: var(--n-option-opacity-disabled);
 `)]),L(`check`,`
 font-size: 16px;
 position: absolute;
 right: calc(var(--n-option-padding-right) - 4px);
 top: calc(50% - 7px);
 color: var(--n-option-check-color);
 transition: color .3s var(--n-bezier);
 `,[j({enterScale:`0.5`})])])]),vt=Z({name:`InternalSelectMenu`,props:Object.assign(Object.assign({},H.props),{clsPrefix:{type:String,required:!0},scrollable:{type:Boolean,default:!0},treeMate:{type:Object,required:!0},multiple:Boolean,size:{type:String,default:`medium`},value:{type:[String,Number,Array],default:null},autoPending:Boolean,virtualScroll:{type:Boolean,default:!0},show:{type:Boolean,default:!0},labelField:{type:String,default:`label`},valueField:{type:String,default:`value`},loading:Boolean,focusable:Boolean,renderLabel:Function,renderOption:Function,nodeProps:Function,showCheckmark:{type:Boolean,default:!0},onMousedown:Function,onScroll:Function,onFocus:Function,onBlur:Function,onKeyup:Function,onKeydown:Function,onTabOut:Function,onMouseenter:Function,onMouseleave:Function,onResize:Function,resetMenuOnOptionsChange:{type:Boolean,default:!0},inlineThemeDisabled:Boolean,scrollbarProps:Object,onToggle:Function}),setup(e){let{mergedClsPrefixRef:t,mergedRtlRef:n,mergedComponentPropsRef:r}=ye(e),i=S(`InternalSelectMenu`,n,t),a=H(`InternalSelectMenu`,`-internal-select-menu`,_t,ie,e,R(e,`clsPrefix`)),o=W(null),s=W(null),c=W(null),u=N(()=>e.treeMate.getFlattenedNodes()),d=N(()=>qe(u.value)),h=W(null);function g(){let{treeMate:t}=e,n=null,{value:r}=e;r===null?n=t.getFirstAvailableNode():(n=e.multiple?t.getNode((r||[])[(r||[]).length-1]):t.getNode(r),(!n||n.disabled)&&(n=t.getFirstAvailableNode())),I(n||null)}function _(){let{value:t}=h;t&&!e.treeMate.getNode(t.key)&&(h.value=null)}let v;ue(()=>e.show,t=>{t?v=ue(()=>e.treeMate,()=>{e.resetMenuOnOptionsChange?(e.autoPending?g():_(),pe(ae)):_()},{immediate:!0}):v?.()},{immediate:!0}),me(()=>{v?.()});let y=N(()=>m(a.value.self[q(`optionHeight`,e.size)])),b=N(()=>l(a.value.self[q(`padding`,e.size)])),x=N(()=>e.multiple&&Array.isArray(e.value)?new Set(e.value):new Set),w=N(()=>{let e=u.value;return e&&e.length===0}),T=N(()=>r?.value?.Select?.renderEmpty);function ee(t){let{onToggle:n}=e;n&&n(t)}function E(t){let{onScroll:n}=e;n&&n(t)}function D(e){var t;(t=c.value)==null||t.sync(),E(e)}function O(){var e;(e=c.value)==null||e.sync()}function k(){let{value:e}=h;return e||null}function te(e,t){t.disabled||I(t,!1)}function j(e,t){t.disabled||ee(t)}function M(t){var n;A(t,`action`)||(n=e.onKeyup)==null||n.call(e,t)}function ne(t){var n;A(t,`action`)||(n=e.onKeydown)==null||n.call(e,t)}function re(t){var n;(n=e.onMousedown)==null||n.call(e,t),!e.focusable&&t.preventDefault()}function P(){let{value:e}=h;e&&I(e.getNext({loop:!0}),!0)}function F(){let{value:e}=h;e&&I(e.getPrev({loop:!0}),!0)}function I(e,t=!1){h.value=e,t&&ae()}function ae(){var t,n;let r=h.value;if(!r)return;let i=d.value(r.key);i!==null&&(e.virtualScroll?(t=s.value)==null||t.scrollTo({index:i}):(n=c.value)==null||n.scrollTo({index:i,elSize:y.value}))}function oe(t){var n;o.value?.contains(t.target)&&((n=e.onFocus)==null||n.call(e,t))}function L(t){var n;o.value?.contains(t.relatedTarget)||(n=e.onBlur)==null||n.call(e,t)}ve(p,{handleOptionMouseEnter:te,handleOptionClick:j,valueSetRef:x,pendingTmNodeRef:h,nodePropsRef:R(e,`nodeProps`),showCheckmarkRef:R(e,`showCheckmark`),multipleRef:R(e,`multiple`),valueRef:R(e,`value`),renderLabelRef:R(e,`renderLabel`),renderOptionRef:R(e,`renderOption`),labelFieldRef:R(e,`labelField`),valueFieldRef:R(e,`valueField`)}),ve(f,o),fe(()=>{let{value:e}=c;e&&e.sync()});let z=N(()=>{let{size:t}=e,{common:{cubicBezierEaseInOut:n},self:{height:r,borderRadius:i,color:o,groupHeaderTextColor:s,actionDividerColor:c,optionTextColorPressed:u,optionTextColor:d,optionTextColorDisabled:f,optionTextColorActive:p,optionOpacityDisabled:m,optionCheckColor:h,actionTextColor:g,optionColorPending:_,optionColorActive:v,loadingColor:y,loadingSize:b,optionColorActivePending:x,[q(`optionFontSize`,t)]:S,[q(`optionHeight`,t)]:C,[q(`optionPadding`,t)]:w}}=a.value;return{"--n-height":r,"--n-action-divider-color":c,"--n-action-text-color":g,"--n-bezier":n,"--n-border-radius":i,"--n-color":o,"--n-option-font-size":S,"--n-group-header-text-color":s,"--n-option-check-color":h,"--n-option-color-pending":_,"--n-option-color-active":v,"--n-option-color-active-pending":x,"--n-option-height":C,"--n-option-opacity-disabled":m,"--n-option-text-color":d,"--n-option-text-color-active":p,"--n-option-text-color-disabled":f,"--n-option-text-color-pressed":u,"--n-option-padding":w,"--n-option-padding-left":l(w,`left`),"--n-option-padding-right":l(w,`right`),"--n-loading-color":y,"--n-loading-size":b}}),{inlineThemeDisabled:B}=e,V=B?C(`internal-select-menu`,N(()=>e.size[0]),z,e):void 0,U={selfRef:o,next:P,prev:F,getPendingTmNode:k};return Ce(o,e.onResize),Object.assign({mergedTheme:a,mergedClsPrefix:t,rtlEnabled:i,virtualListRef:s,scrollbarRef:c,itemSize:y,padding:b,flattenedNodes:u,empty:w,mergedRenderEmpty:T,virtualListContainer(){let{value:e}=s;return e?.listElRef},virtualListContent(){let{value:e}=s;return e?.itemsElRef},doScroll:E,handleFocusin:oe,handleFocusout:L,handleKeyUp:M,handleKeyDown:ne,handleMouseDown:re,handleVirtualListResize:O,handleVirtualListScroll:D,cssVars:B?void 0:z,themeClass:V?.themeClass,onRender:V?.onRender},U)},render(){let{$slots:e,virtualScroll:t,clsPrefix:n,mergedTheme:r,themeClass:i,onRender:a}=this;return a?.(),X(`div`,{ref:`selfRef`,tabindex:this.focusable?0:-1,class:[`${n}-base-select-menu`,`${n}-base-select-menu--${this.size}-size`,this.rtlEnabled&&`${n}-base-select-menu--rtl`,i,this.multiple&&`${n}-base-select-menu--multiple`],style:this.cssVars,onFocusin:this.handleFocusin,onFocusout:this.handleFocusout,onKeyup:this.handleKeyUp,onKeydown:this.handleKeyDown,onMousedown:this.handleMouseDown,onMouseenter:this.onMouseenter,onMouseleave:this.onMouseleave},w(e.header,e=>e&&X(`div`,{class:`${n}-base-select-menu__header`,"data-header":!0,key:`header`},e)),this.loading?X(`div`,{class:`${n}-base-select-menu__loading`},X(b,{clsPrefix:n,strokeWidth:20})):this.empty?X(`div`,{class:`${n}-base-select-menu__empty`,"data-empty":!0},u(e.empty,()=>[this.mergedRenderEmpty?.call(this)||X(pt,{theme:r.peers.Empty,themeOverrides:r.peerOverrides.Empty,size:this.size})])):X(x,Object.assign({ref:`scrollbarRef`,theme:r.peers.Scrollbar,themeOverrides:r.peerOverrides.Scrollbar,scrollable:this.scrollable,container:t?this.virtualListContainer:void 0,content:t?this.virtualListContent:void 0,onScroll:t?void 0:this.doScroll},this.scrollbarProps),{default:()=>t?X(D,{ref:`virtualListRef`,class:`${n}-virtual-list`,items:this.flattenedNodes,itemSize:this.itemSize,showScrollbar:!1,paddingTop:this.padding.top,paddingBottom:this.padding.bottom,onResize:this.handleVirtualListResize,onScroll:this.handleVirtualListScroll,itemResizable:!0},{default:({item:e})=>e.isGroup?X(mt,{key:e.key,clsPrefix:n,tmNode:e}):e.ignored?null:X(gt,{clsPrefix:n,key:e.key,tmNode:e})}):X(`div`,{class:`${n}-base-select-menu-option-wrapper`,style:{paddingTop:this.padding.top,paddingBottom:this.padding.bottom}},this.flattenedNodes.map(e=>e.isGroup?X(mt,{key:e.key,clsPrefix:n,tmNode:e}):X(gt,{clsPrefix:n,key:e.key,tmNode:e})))}),w(e.action,e=>e&&[X(`div`,{class:`${n}-base-select-menu__action`,"data-action":!0,key:`action`},e),X(O,{onFocus:this.onTabOut,key:`focus-detector`})]))}});function yt(e){let{textColor2:t,primaryColorHover:n,primaryColorPressed:r,primaryColor:i,infoColor:a,successColor:o,warningColor:s,errorColor:c,baseColor:l,borderColor:u,opacityDisabled:d,tagColor:f,closeIconColor:p,closeIconColorHover:m,closeIconColorPressed:h,borderRadiusSmall:g,fontSizeMini:_,fontSizeTiny:v,fontSizeSmall:y,fontSizeMedium:b,heightMini:x,heightTiny:S,heightSmall:C,heightMedium:w,closeColorHover:T,closeColorPressed:ee,buttonColor2Hover:E,buttonColor2Pressed:D,fontWeightStrong:O}=e;return Object.assign(Object.assign({},le),{closeBorderRadius:g,heightTiny:x,heightSmall:S,heightMedium:C,heightLarge:w,borderRadius:g,opacityDisabled:d,fontSizeTiny:_,fontSizeSmall:v,fontSizeMedium:y,fontSizeLarge:b,fontWeightStrong:O,textColorCheckable:t,textColorHoverCheckable:t,textColorPressedCheckable:t,textColorChecked:l,colorCheckable:`#0000`,colorHoverCheckable:E,colorPressedCheckable:D,colorChecked:i,colorCheckedHover:n,colorCheckedPressed:r,border:`1px solid ${u}`,textColor:t,color:f,colorBordered:`rgb(250, 250, 252)`,closeIconColor:p,closeIconColorHover:m,closeIconColorPressed:h,closeColorHover:T,closeColorPressed:ee,borderPrimary:`1px solid ${K(i,{alpha:.3})}`,textColorPrimary:i,colorPrimary:K(i,{alpha:.12}),colorBorderedPrimary:K(i,{alpha:.1}),closeIconColorPrimary:i,closeIconColorHoverPrimary:i,closeIconColorPressedPrimary:i,closeColorHoverPrimary:K(i,{alpha:.12}),closeColorPressedPrimary:K(i,{alpha:.18}),borderInfo:`1px solid ${K(a,{alpha:.3})}`,textColorInfo:a,colorInfo:K(a,{alpha:.12}),colorBorderedInfo:K(a,{alpha:.1}),closeIconColorInfo:a,closeIconColorHoverInfo:a,closeIconColorPressedInfo:a,closeColorHoverInfo:K(a,{alpha:.12}),closeColorPressedInfo:K(a,{alpha:.18}),borderSuccess:`1px solid ${K(o,{alpha:.3})}`,textColorSuccess:o,colorSuccess:K(o,{alpha:.12}),colorBorderedSuccess:K(o,{alpha:.1}),closeIconColorSuccess:o,closeIconColorHoverSuccess:o,closeIconColorPressedSuccess:o,closeColorHoverSuccess:K(o,{alpha:.12}),closeColorPressedSuccess:K(o,{alpha:.18}),borderWarning:`1px solid ${K(s,{alpha:.35})}`,textColorWarning:s,colorWarning:K(s,{alpha:.15}),colorBorderedWarning:K(s,{alpha:.12}),closeIconColorWarning:s,closeIconColorHoverWarning:s,closeIconColorPressedWarning:s,closeColorHoverWarning:K(s,{alpha:.12}),closeColorPressedWarning:K(s,{alpha:.18}),borderError:`1px solid ${K(c,{alpha:.23})}`,textColorError:c,colorError:K(c,{alpha:.1}),colorBorderedError:K(c,{alpha:.08}),closeIconColorError:c,closeIconColorHoverError:c,closeIconColorPressedError:c,closeColorHoverError:K(c,{alpha:.12}),closeColorPressedError:K(c,{alpha:.18})})}var bt={name:`Tag`,common:P,self:yt},xt={color:Object,type:{type:String,default:`default`},round:Boolean,size:String,closable:Boolean,disabled:{type:Boolean,default:void 0}},St=G(`tag`,`
 --n-close-margin: var(--n-close-margin-top) var(--n-close-margin-right) var(--n-close-margin-bottom) var(--n-close-margin-left);
 white-space: nowrap;
 position: relative;
 box-sizing: border-box;
 cursor: default;
 display: inline-flex;
 align-items: center;
 flex-wrap: nowrap;
 padding: var(--n-padding);
 border-radius: var(--n-border-radius);
 color: var(--n-text-color);
 background-color: var(--n-color);
 transition: 
 border-color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier),
 opacity .3s var(--n-bezier);
 line-height: 1;
 height: var(--n-height);
 font-size: var(--n-font-size);
`,[z(`strong`,`
 font-weight: var(--n-font-weight-strong);
 `),L(`border`,`
 pointer-events: none;
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 border-radius: inherit;
 border: var(--n-border);
 transition: border-color .3s var(--n-bezier);
 `),L(`icon`,`
 display: flex;
 margin: 0 4px 0 0;
 color: var(--n-text-color);
 transition: color .3s var(--n-bezier);
 font-size: var(--n-avatar-size-override);
 `),L(`avatar`,`
 display: flex;
 margin: 0 6px 0 0;
 `),L(`close`,`
 margin: var(--n-close-margin);
 transition:
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 `),z(`round`,`
 padding: 0 calc(var(--n-height) / 3);
 border-radius: calc(var(--n-height) / 2);
 `,[L(`icon`,`
 margin: 0 4px 0 calc((var(--n-height) - 8px) / -2);
 `),L(`avatar`,`
 margin: 0 6px 0 calc((var(--n-height) - 8px) / -2);
 `),z(`closable`,`
 padding: 0 calc(var(--n-height) / 4) 0 calc(var(--n-height) / 3);
 `)]),z(`icon, avatar`,[z(`round`,`
 padding: 0 calc(var(--n-height) / 3) 0 calc(var(--n-height) / 2);
 `)]),z(`disabled`,`
 cursor: not-allowed !important;
 opacity: var(--n-opacity-disabled);
 `),z(`checkable`,`
 cursor: pointer;
 box-shadow: none;
 color: var(--n-text-color-checkable);
 background-color: var(--n-color-checkable);
 `,[V(`disabled`,[U(`&:hover`,`background-color: var(--n-color-hover-checkable);`,[V(`checked`,`color: var(--n-text-color-hover-checkable);`)]),U(`&:active`,`background-color: var(--n-color-pressed-checkable);`,[V(`checked`,`color: var(--n-text-color-pressed-checkable);`)])]),z(`checked`,`
 color: var(--n-text-color-checked);
 background-color: var(--n-color-checked);
 `,[V(`disabled`,[U(`&:hover`,`background-color: var(--n-color-checked-hover);`),U(`&:active`,`background-color: var(--n-color-checked-pressed);`)])])])]),Ct=Object.assign(Object.assign(Object.assign({},H.props),xt),{bordered:{type:Boolean,default:void 0},checked:Boolean,checkable:Boolean,strong:Boolean,triggerClickOnClose:Boolean,onClose:[Array,Function],onMouseenter:Function,onMouseleave:Function,"onUpdate:checked":Function,onUpdateChecked:Function,internalCloseFocusable:{type:Boolean,default:!0},internalCloseIsButtonTag:{type:Boolean,default:!0},onCheckedChange:Function}),wt=oe(`n-tag`),Tt=Z({name:`Tag`,props:Ct,slots:Object,setup(t){let n=W(null),{mergedBorderedRef:r,mergedClsPrefixRef:i,inlineThemeDisabled:a,mergedRtlRef:o,mergedComponentPropsRef:s}=ye(t),c=N(()=>t.size||s?.value?.Tag?.size||`medium`),u=H(`Tag`,`-tag`,St,bt,t,i);ve(wt,{roundRef:R(t,`round`)});function f(){if(!t.disabled&&t.checkable){let{checked:e,onCheckedChange:n,onUpdateChecked:r,"onUpdate:checked":i}=t;r&&r(!e),i&&i(!e),n&&n(!e)}}function p(e){if(t.triggerClickOnClose||e.stopPropagation(),!t.disabled){let{onClose:n}=t;n&&d(n,e)}}let m={setTextContent(e){let{value:t}=n;t&&(t.textContent=e)}},h=S(`Tag`,o,i),g=N(()=>{let{type:e,color:{color:n,textColor:i}={}}=t,a=c.value,{common:{cubicBezierEaseInOut:o},self:{padding:s,closeMargin:d,borderRadius:f,opacityDisabled:p,textColorCheckable:m,textColorHoverCheckable:h,textColorPressedCheckable:g,textColorChecked:_,colorCheckable:v,colorHoverCheckable:y,colorPressedCheckable:b,colorChecked:x,colorCheckedHover:S,colorCheckedPressed:C,closeBorderRadius:w,fontWeightStrong:T,[q(`colorBordered`,e)]:ee,[q(`closeSize`,a)]:E,[q(`closeIconSize`,a)]:D,[q(`fontSize`,a)]:O,[q(`height`,a)]:k,[q(`color`,e)]:te,[q(`textColor`,e)]:A,[q(`border`,e)]:j,[q(`closeIconColor`,e)]:M,[q(`closeIconColorHover`,e)]:ne,[q(`closeIconColorPressed`,e)]:re,[q(`closeColorHover`,e)]:N,[q(`closeColorPressed`,e)]:P}}=u.value,F=l(d);return{"--n-font-weight-strong":T,"--n-avatar-size-override":`calc(${k} - 8px)`,"--n-bezier":o,"--n-border-radius":f,"--n-border":j,"--n-close-icon-size":D,"--n-close-color-pressed":P,"--n-close-color-hover":N,"--n-close-border-radius":w,"--n-close-icon-color":M,"--n-close-icon-color-hover":ne,"--n-close-icon-color-pressed":re,"--n-close-icon-color-disabled":M,"--n-close-margin-top":F.top,"--n-close-margin-right":F.right,"--n-close-margin-bottom":F.bottom,"--n-close-margin-left":F.left,"--n-close-size":E,"--n-color":n||(r.value?ee:te),"--n-color-checkable":v,"--n-color-checked":x,"--n-color-checked-hover":S,"--n-color-checked-pressed":C,"--n-color-hover-checkable":y,"--n-color-pressed-checkable":b,"--n-font-size":O,"--n-height":k,"--n-opacity-disabled":p,"--n-padding":s,"--n-text-color":i||A,"--n-text-color-checkable":m,"--n-text-color-checked":_,"--n-text-color-hover-checkable":h,"--n-text-color-pressed-checkable":g}}),_=a?C(`tag`,N(()=>{let n=``,{type:i,color:{color:a,textColor:o}={}}=t;return n+=i[0],n+=c.value[0],a&&(n+=`a${e(a)}`),o&&(n+=`b${e(o)}`),r.value&&(n+=`c`),n}),g,t):void 0;return Object.assign(Object.assign({},m),{rtlEnabled:h,mergedClsPrefix:i,contentRef:n,mergedBordered:r,handleClick:f,handleCloseClick:p,cssVars:a?void 0:g,themeClass:_?.themeClass,onRender:_?.onRender})},render(){var e;let{mergedClsPrefix:t,rtlEnabled:n,closable:r,color:{borderColor:i}={},round:a,onRender:o,$slots:s}=this;o?.();let c=w(s.avatar,e=>e&&X(`div`,{class:`${t}-tag__avatar`},e)),l=w(s.icon,e=>e&&X(`div`,{class:`${t}-tag__icon`},e));return X(`div`,{class:[`${t}-tag`,this.themeClass,{[`${t}-tag--rtl`]:n,[`${t}-tag--strong`]:this.strong,[`${t}-tag--disabled`]:this.disabled,[`${t}-tag--checkable`]:this.checkable,[`${t}-tag--checked`]:this.checkable&&this.checked,[`${t}-tag--round`]:a,[`${t}-tag--avatar`]:c,[`${t}-tag--icon`]:l,[`${t}-tag--closable`]:r}],style:this.cssVars,onClick:this.handleClick,onMouseenter:this.onMouseenter,onMouseleave:this.onMouseleave},l||c,X(`span`,{class:`${t}-tag__content`,ref:`contentRef`},(e=this.$slots).default?.call(e)),!this.checkable&&r?X(Ae,{clsPrefix:t,class:`${t}-tag__close`,disabled:this.disabled,onClick:this.handleCloseClick,focusable:this.internalCloseFocusable,round:a,isButtonTag:this.internalCloseIsButtonTag,absolute:!0}):null,!this.checkable&&this.mergedBordered?X(`div`,{class:`${t}-tag__border`,style:{borderColor:i}}):null)}}),Et=U([G(`base-selection`,`
 --n-padding-single: var(--n-padding-single-top) var(--n-padding-single-right) var(--n-padding-single-bottom) var(--n-padding-single-left);
 --n-padding-multiple: var(--n-padding-multiple-top) var(--n-padding-multiple-right) var(--n-padding-multiple-bottom) var(--n-padding-multiple-left);
 position: relative;
 z-index: auto;
 box-shadow: none;
 width: 100%;
 max-width: 100%;
 display: inline-block;
 vertical-align: bottom;
 border-radius: var(--n-border-radius);
 min-height: var(--n-height);
 line-height: 1.5;
 font-size: var(--n-font-size);
 `,[G(`base-loading`,`
 color: var(--n-loading-color);
 `),G(`base-selection-tags`,`min-height: var(--n-height);`),L(`border, state-border`,`
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 pointer-events: none;
 border: var(--n-border);
 border-radius: inherit;
 transition:
 box-shadow .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `),L(`state-border`,`
 z-index: 1;
 border-color: #0000;
 `),G(`base-suffix`,`
 cursor: pointer;
 position: absolute;
 top: 50%;
 transform: translateY(-50%);
 right: 10px;
 `,[L(`arrow`,`
 font-size: var(--n-arrow-size);
 color: var(--n-arrow-color);
 transition: color .3s var(--n-bezier);
 `)]),G(`base-selection-overlay`,`
 display: flex;
 align-items: center;
 white-space: nowrap;
 pointer-events: none;
 position: absolute;
 top: 0;
 right: 0;
 bottom: 0;
 left: 0;
 padding: var(--n-padding-single);
 transition: color .3s var(--n-bezier);
 `,[L(`wrapper`,`
 flex-basis: 0;
 flex-grow: 1;
 overflow: hidden;
 text-overflow: ellipsis;
 `)]),G(`base-selection-placeholder`,`
 color: var(--n-placeholder-color);
 `,[L(`inner`,`
 max-width: 100%;
 overflow: hidden;
 `)]),G(`base-selection-tags`,`
 cursor: pointer;
 outline: none;
 box-sizing: border-box;
 position: relative;
 z-index: auto;
 display: flex;
 padding: var(--n-padding-multiple);
 flex-wrap: wrap;
 align-items: center;
 width: 100%;
 vertical-align: bottom;
 background-color: var(--n-color);
 border-radius: inherit;
 transition:
 color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 `),G(`base-selection-label`,`
 height: var(--n-height);
 display: inline-flex;
 width: 100%;
 vertical-align: bottom;
 cursor: pointer;
 outline: none;
 z-index: auto;
 box-sizing: border-box;
 position: relative;
 transition:
 color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 border-radius: inherit;
 background-color: var(--n-color);
 align-items: center;
 `,[G(`base-selection-input`,`
 font-size: inherit;
 line-height: inherit;
 outline: none;
 cursor: pointer;
 box-sizing: border-box;
 border:none;
 width: 100%;
 padding: var(--n-padding-single);
 background-color: #0000;
 color: var(--n-text-color);
 transition: color .3s var(--n-bezier);
 caret-color: var(--n-caret-color);
 `,[L(`content`,`
 text-overflow: ellipsis;
 overflow: hidden;
 white-space: nowrap; 
 `)]),L(`render-label`,`
 color: var(--n-text-color);
 `)]),V(`disabled`,[U(`&:hover`,[L(`state-border`,`
 box-shadow: var(--n-box-shadow-hover);
 border: var(--n-border-hover);
 `)]),z(`focus`,[L(`state-border`,`
 box-shadow: var(--n-box-shadow-focus);
 border: var(--n-border-focus);
 `)]),z(`active`,[L(`state-border`,`
 box-shadow: var(--n-box-shadow-active);
 border: var(--n-border-active);
 `),G(`base-selection-label`,`background-color: var(--n-color-active);`),G(`base-selection-tags`,`background-color: var(--n-color-active);`)])]),z(`disabled`,`cursor: not-allowed;`,[L(`arrow`,`
 color: var(--n-arrow-color-disabled);
 `),G(`base-selection-label`,`
 cursor: not-allowed;
 background-color: var(--n-color-disabled);
 `,[G(`base-selection-input`,`
 cursor: not-allowed;
 color: var(--n-text-color-disabled);
 `),L(`render-label`,`
 color: var(--n-text-color-disabled);
 `)]),G(`base-selection-tags`,`
 cursor: not-allowed;
 background-color: var(--n-color-disabled);
 `),G(`base-selection-placeholder`,`
 cursor: not-allowed;
 color: var(--n-placeholder-color-disabled);
 `)]),G(`base-selection-input-tag`,`
 height: calc(var(--n-height) - 6px);
 line-height: calc(var(--n-height) - 6px);
 outline: none;
 display: none;
 position: relative;
 margin-bottom: 3px;
 max-width: 100%;
 vertical-align: bottom;
 `,[L(`input`,`
 font-size: inherit;
 font-family: inherit;
 min-width: 1px;
 padding: 0;
 background-color: #0000;
 outline: none;
 border: none;
 max-width: 100%;
 overflow: hidden;
 width: 1em;
 line-height: inherit;
 cursor: pointer;
 color: var(--n-text-color);
 caret-color: var(--n-caret-color);
 `),L(`mirror`,`
 position: absolute;
 left: 0;
 top: 0;
 white-space: pre;
 visibility: hidden;
 user-select: none;
 -webkit-user-select: none;
 opacity: 0;
 `)]),[`warning`,`error`].map(e=>z(`${e}-status`,[L(`state-border`,`border: var(--n-border-${e});`),V(`disabled`,[U(`&:hover`,[L(`state-border`,`
 box-shadow: var(--n-box-shadow-hover-${e});
 border: var(--n-border-hover-${e});
 `)]),z(`active`,[L(`state-border`,`
 box-shadow: var(--n-box-shadow-active-${e});
 border: var(--n-border-active-${e});
 `),G(`base-selection-label`,`background-color: var(--n-color-active-${e});`),G(`base-selection-tags`,`background-color: var(--n-color-active-${e});`)]),z(`focus`,[L(`state-border`,`
 box-shadow: var(--n-box-shadow-focus-${e});
 border: var(--n-border-focus-${e});
 `)])])]))]),G(`base-selection-popover`,`
 margin-bottom: -3px;
 display: flex;
 flex-wrap: wrap;
 margin-right: -8px;
 `),G(`base-selection-tag-wrapper`,`
 max-width: 100%;
 display: inline-flex;
 padding: 0 7px 3px 0;
 `,[U(`&:last-child`,`padding-right: 0;`),G(`tag`,`
 font-size: 14px;
 max-width: 100%;
 `,[L(`content`,`
 line-height: 1.25;
 text-overflow: ellipsis;
 overflow: hidden;
 `)])])]),Dt=Z({name:`InternalSelection`,props:Object.assign(Object.assign({},H.props),{clsPrefix:{type:String,required:!0},bordered:{type:Boolean,default:void 0},active:Boolean,pattern:{type:String,default:``},placeholder:String,selectedOption:{type:Object,default:null},selectedOptions:{type:Array,default:null},labelField:{type:String,default:`label`},valueField:{type:String,default:`value`},multiple:Boolean,filterable:Boolean,clearable:Boolean,disabled:Boolean,size:{type:String,default:`medium`},loading:Boolean,autofocus:Boolean,showArrow:{type:Boolean,default:!0},inputProps:Object,focused:Boolean,renderTag:Function,onKeydown:Function,onClick:Function,onBlur:Function,onFocus:Function,onDeleteOption:Function,maxTagCount:[String,Number],ellipsisTagPopoverProps:Object,onClear:Function,onPatternInput:Function,onPatternFocus:Function,onPatternBlur:Function,renderLabel:Function,status:String,inlineThemeDisabled:Boolean,ignoreComposition:{type:Boolean,default:!0},onResize:Function}),setup(e){let{mergedClsPrefixRef:t,mergedRtlRef:n}=ye(e),r=S(`InternalSelection`,n,t),i=W(null),a=W(null),o=W(null),s=W(null),c=W(null),u=W(null),d=W(null),f=W(null),p=W(null),m=W(null),h=W(!1),g=W(!1),_=W(!1),v=H(`InternalSelection`,`-internal-selection`,Et,_e,e,R(e,`clsPrefix`)),y=N(()=>e.clearable&&!e.disabled&&(_.value||e.active)),b=N(()=>e.selectedOption?e.renderTag?e.renderTag({option:e.selectedOption,handleClose:()=>{}}):e.renderLabel?e.renderLabel(e.selectedOption,!0):$(e.selectedOption[e.labelField],e.selectedOption,!0):e.placeholder),x=N(()=>{let t=e.selectedOption;if(t)return t[e.labelField]}),w=N(()=>e.multiple?!!(Array.isArray(e.selectedOptions)&&e.selectedOptions.length):e.selectedOption!==null);function T(){var t;let{value:n}=i;if(n){let{value:r}=a;r&&(r.style.width=`${n.offsetWidth}px`,e.maxTagCount!==`responsive`&&((t=p.value)==null||t.sync({showAllItemsBeforeCalculate:!1})))}}function ee(){let{value:e}=m;e&&(e.style.display=`none`)}function E(){let{value:e}=m;e&&(e.style.display=`inline-block`)}ue(R(e,`active`),e=>{e||ee()}),ue(R(e,`pattern`),()=>{e.multiple&&pe(T)});function D(t){let{onFocus:n}=e;n&&n(t)}function O(t){let{onBlur:n}=e;n&&n(t)}function k(t){let{onDeleteOption:n}=e;n&&n(t)}function te(t){let{onClear:n}=e;n&&n(t)}function A(t){let{onPatternInput:n}=e;n&&n(t)}function j(e){(!e.relatedTarget||!o.value?.contains(e.relatedTarget))&&D(e)}function M(e){o.value?.contains(e.relatedTarget)||O(e)}function ne(e){te(e)}function re(){_.value=!0}function P(){_.value=!1}function F(t){!e.active||!e.filterable||t.target!==a.value&&t.preventDefault()}function ie(e){k(e)}let I=W(!1);function oe(t){if(t.key===`Backspace`&&!I.value&&!e.pattern.length){let{selectedOptions:t}=e;t?.length&&ie(t[t.length-1])}}let L=null;function z(t){let{value:n}=i;n&&(n.textContent=t.target.value,T()),e.ignoreComposition&&I.value?L=t:A(t)}function B(){I.value=!0}function V(){I.value=!1,e.ignoreComposition&&A(L),L=null}function U(t){var n;g.value=!0,(n=e.onPatternFocus)==null||n.call(e,t)}function G(t){var n;g.value=!1,(n=e.onPatternBlur)==null||n.call(e,t)}function se(){var t,n;if(e.filterable)g.value=!1,(t=u.value)==null||t.blur(),(n=a.value)==null||n.blur();else if(e.multiple){let{value:e}=s;e?.blur()}else{let{value:e}=c;e?.blur()}}function ce(){var t,n,r;e.filterable?(g.value=!1,(t=u.value)==null||t.focus()):e.multiple?(n=s.value)==null||n.focus():(r=c.value)==null||r.focus()}function K(){let{value:e}=a;e&&(E(),e.focus())}function le(){let{value:e}=a;e&&e.blur()}function de(e){let{value:t}=d;t&&t.setTextContent(`+${e}`)}function J(){let{value:e}=f;return e}function Y(){return a.value}let X=null;function me(){X!==null&&window.clearTimeout(X)}function he(){e.active||(me(),X=window.setTimeout(()=>{w.value&&(h.value=!0)},100))}function ge(){me()}function Z(e){e||(me(),h.value=!1)}ue(w,e=>{e||(h.value=!1)}),fe(()=>{ae(()=>{let t=u.value;t&&(e.disabled?t.removeAttribute(`tabindex`):t.tabIndex=g.value?-1:0)})}),Ce(o,e.onResize);let{inlineThemeDisabled:ve}=e,be=N(()=>{let{size:t}=e,{common:{cubicBezierEaseInOut:n},self:{fontWeight:r,borderRadius:i,color:a,placeholderColor:o,textColor:s,paddingSingle:c,paddingMultiple:u,caretColor:d,colorDisabled:f,textColorDisabled:p,placeholderColorDisabled:m,colorActive:h,boxShadowFocus:g,boxShadowActive:_,boxShadowHover:y,border:b,borderFocus:x,borderHover:S,borderActive:C,arrowColor:w,arrowColorDisabled:T,loadingColor:ee,colorActiveWarning:E,boxShadowFocusWarning:D,boxShadowActiveWarning:O,boxShadowHoverWarning:k,borderWarning:te,borderFocusWarning:A,borderHoverWarning:j,borderActiveWarning:M,colorActiveError:ne,boxShadowFocusError:re,boxShadowActiveError:N,boxShadowHoverError:P,borderError:F,borderFocusError:ie,borderHoverError:I,borderActiveError:ae,clearColor:oe,clearColorHover:L,clearColorPressed:R,clearSize:z,arrowSize:B,[q(`height`,t)]:V,[q(`fontSize`,t)]:H}}=v.value,U=l(c),W=l(u);return{"--n-bezier":n,"--n-border":b,"--n-border-active":C,"--n-border-focus":x,"--n-border-hover":S,"--n-border-radius":i,"--n-box-shadow-active":_,"--n-box-shadow-focus":g,"--n-box-shadow-hover":y,"--n-caret-color":d,"--n-color":a,"--n-color-active":h,"--n-color-disabled":f,"--n-font-size":H,"--n-height":V,"--n-padding-single-top":U.top,"--n-padding-multiple-top":W.top,"--n-padding-single-right":U.right,"--n-padding-multiple-right":W.right,"--n-padding-single-left":U.left,"--n-padding-multiple-left":W.left,"--n-padding-single-bottom":U.bottom,"--n-padding-multiple-bottom":W.bottom,"--n-placeholder-color":o,"--n-placeholder-color-disabled":m,"--n-text-color":s,"--n-text-color-disabled":p,"--n-arrow-color":w,"--n-arrow-color-disabled":T,"--n-loading-color":ee,"--n-color-active-warning":E,"--n-box-shadow-focus-warning":D,"--n-box-shadow-active-warning":O,"--n-box-shadow-hover-warning":k,"--n-border-warning":te,"--n-border-focus-warning":A,"--n-border-hover-warning":j,"--n-border-active-warning":M,"--n-color-active-error":ne,"--n-box-shadow-focus-error":re,"--n-box-shadow-active-error":N,"--n-box-shadow-hover-error":P,"--n-border-error":F,"--n-border-focus-error":ie,"--n-border-hover-error":I,"--n-border-active-error":ae,"--n-clear-size":z,"--n-clear-color":oe,"--n-clear-color-hover":L,"--n-clear-color-pressed":R,"--n-arrow-size":B,"--n-font-weight":r}}),Q=ve?C(`internal-selection`,N(()=>e.size[0]),be,e):void 0;return{mergedTheme:v,mergedClearable:y,mergedClsPrefix:t,rtlEnabled:r,patternInputFocused:g,filterablePlaceholder:b,label:x,selected:w,showTagsPanel:h,isComposing:I,counterRef:d,counterWrapperRef:f,patternInputMirrorRef:i,patternInputRef:a,selfRef:o,multipleElRef:s,singleElRef:c,patternInputWrapperRef:u,overflowRef:p,inputTagElRef:m,handleMouseDown:F,handleFocusin:j,handleClear:ne,handleMouseEnter:re,handleMouseLeave:P,handleDeleteOption:ie,handlePatternKeyDown:oe,handlePatternInputInput:z,handlePatternInputBlur:G,handlePatternInputFocus:U,handleMouseEnterCounter:he,handleMouseLeaveCounter:ge,handleFocusout:M,handleCompositionEnd:V,handleCompositionStart:B,onPopoverUpdateShow:Z,focus:ce,focusInput:K,blur:se,blurInput:le,updateCounter:de,getCounter:J,getTail:Y,renderLabel:e.renderLabel,cssVars:ve?void 0:be,themeClass:Q?.themeClass,onRender:Q?.onRender}},render(){let{status:e,multiple:t,size:n,disabled:r,filterable:i,maxTagCount:a,bordered:o,clsPrefix:s,ellipsisTagPopoverProps:c,onRender:l,renderTag:u,renderLabel:d}=this;l?.();let f=a===`responsive`,p=typeof a==`number`,m=f||p,h=X(T,null,{default:()=>X(k,{clsPrefix:s,loading:this.loading,showArrow:this.showArrow,showClear:this.mergedClearable&&this.selected,onClear:this.handleClear},{default:()=>{var e;return(e=this.$slots).arrow?.call(e)}})}),g;if(t){let{labelField:e}=this,t=t=>X(`div`,{class:`${s}-base-selection-tag-wrapper`,key:t.value},u?u({option:t,handleClose:()=>{this.handleDeleteOption(t)}}):X(Tt,{size:n,closable:!t.disabled,disabled:r,onClose:()=>{this.handleDeleteOption(t)},internalCloseIsButtonTag:!1,internalCloseFocusable:!1},{default:()=>d?d(t,!0):$(t[e],t,!0)})),o=()=>(p?this.selectedOptions.slice(0,a):this.selectedOptions).map(t),l=i?X(`div`,{class:`${s}-base-selection-input-tag`,ref:`inputTagElRef`,key:`__input-tag__`},X(`input`,Object.assign({},this.inputProps,{ref:`patternInputRef`,tabindex:-1,disabled:r,value:this.pattern,autofocus:this.autofocus,class:`${s}-base-selection-input-tag__input`,onBlur:this.handlePatternInputBlur,onFocus:this.handlePatternInputFocus,onKeydown:this.handlePatternKeyDown,onInput:this.handlePatternInputInput,onCompositionstart:this.handleCompositionStart,onCompositionend:this.handleCompositionEnd})),X(`span`,{ref:`patternInputMirrorRef`,class:`${s}-base-selection-input-tag__mirror`},this.pattern)):null,_=f?()=>X(`div`,{class:`${s}-base-selection-tag-wrapper`,ref:`counterWrapperRef`},X(Tt,{size:n,ref:`counterRef`,onMouseenter:this.handleMouseEnterCounter,onMouseleave:this.handleMouseLeaveCounter,disabled:r})):void 0,v;if(p){let e=this.selectedOptions.length-a;e>0&&(v=X(`div`,{class:`${s}-base-selection-tag-wrapper`,key:`__counter__`},X(Tt,{size:n,ref:`counterRef`,onMouseenter:this.handleMouseEnterCounter,disabled:r},{default:()=>`+${e}`})))}let y=f?i?X(Se,{ref:`overflowRef`,updateCounter:this.updateCounter,getCounter:this.getCounter,getTail:this.getTail,style:{width:`100%`,display:`flex`,overflow:`hidden`}},{default:o,counter:_,tail:()=>l}):X(Se,{ref:`overflowRef`,updateCounter:this.updateCounter,getCounter:this.getCounter,style:{width:`100%`,display:`flex`,overflow:`hidden`}},{default:o,counter:_}):p&&v?o().concat(v):o(),b=m?()=>X(`div`,{class:`${s}-base-selection-popover`},f?o():this.selectedOptions.map(t)):void 0,x=m?Object.assign({show:this.showTagsPanel,trigger:`hover`,overlap:!0,placement:`top`,width:`trigger`,onUpdateShow:this.onPopoverUpdateShow,theme:this.mergedTheme.peers.Popover,themeOverrides:this.mergedTheme.peerOverrides.Popover},c):null,S=!this.selected&&(!this.active||!this.pattern&&!this.isComposing)?X(`div`,{class:`${s}-base-selection-placeholder ${s}-base-selection-overlay`},X(`div`,{class:`${s}-base-selection-placeholder__inner`},this.placeholder)):null,C=i?X(`div`,{ref:`patternInputWrapperRef`,class:`${s}-base-selection-tags`},y,f?null:l,h):X(`div`,{ref:`multipleElRef`,class:`${s}-base-selection-tags`,tabindex:r?void 0:0},y,h);g=X(Y,null,m?X(ne,Object.assign({},x,{scrollable:!0,style:`max-height: calc(var(--v-target-height) * 6.6);`}),{trigger:()=>C,default:b}):C,S)}else if(i){let e=this.pattern||this.isComposing,t=this.active?!e:!this.selected,n=this.active?!1:this.selected;g=X(`div`,{ref:`patternInputWrapperRef`,class:`${s}-base-selection-label`,title:this.patternInputFocused?void 0:we(this.label)},X(`input`,Object.assign({},this.inputProps,{ref:`patternInputRef`,class:`${s}-base-selection-input`,value:this.active?this.pattern:``,placeholder:``,readonly:r,disabled:r,tabindex:-1,autofocus:this.autofocus,onFocus:this.handlePatternInputFocus,onBlur:this.handlePatternInputBlur,onInput:this.handlePatternInputInput,onCompositionstart:this.handleCompositionStart,onCompositionend:this.handleCompositionEnd})),n?X(`div`,{class:`${s}-base-selection-label__render-label ${s}-base-selection-overlay`,key:`input`},X(`div`,{class:`${s}-base-selection-overlay__wrapper`},u?u({option:this.selectedOption,handleClose:()=>{}}):d?d(this.selectedOption,!0):$(this.label,this.selectedOption,!0))):null,t?X(`div`,{class:`${s}-base-selection-placeholder ${s}-base-selection-overlay`,key:`placeholder`},X(`div`,{class:`${s}-base-selection-overlay__wrapper`},this.filterablePlaceholder)):null,h)}else g=X(`div`,{ref:`singleElRef`,class:`${s}-base-selection-label`,tabindex:this.disabled?void 0:0},this.label===void 0?X(`div`,{class:`${s}-base-selection-placeholder ${s}-base-selection-overlay`,key:`placeholder`},X(`div`,{class:`${s}-base-selection-placeholder__inner`},this.placeholder)):X(`div`,{class:`${s}-base-selection-input`,title:we(this.label),key:`input`},X(`div`,{class:`${s}-base-selection-input__content`},u?u({option:this.selectedOption,handleClose:()=>{}}):d?d(this.selectedOption,!0):$(this.label,this.selectedOption,!0))),h);return X(`div`,{ref:`selfRef`,class:[`${s}-base-selection`,this.rtlEnabled&&`${s}-base-selection--rtl`,this.themeClass,e&&`${s}-base-selection--${e}-status`,{[`${s}-base-selection--active`]:this.active,[`${s}-base-selection--selected`]:this.selected||this.active&&this.pattern,[`${s}-base-selection--disabled`]:this.disabled,[`${s}-base-selection--multiple`]:this.multiple,[`${s}-base-selection--focus`]:this.focused}],style:this.cssVars,onClick:this.onClick,onMouseenter:this.handleMouseEnter,onMouseleave:this.handleMouseLeave,onKeydown:this.onKeydown,onFocusin:this.handleFocusin,onFocusout:this.handleFocusout,onMousedown:this.handleMouseDown},g,o?X(`div`,{class:`${s}-base-selection__border`}):null,o?X(`div`,{class:`${s}-base-selection__state-border`}):null)}});function Ot(e){return e.type===`group`}function kt(e){return e.type===`ignored`}function At(e,t){try{return!!(1+t.toString().toLowerCase().indexOf(e.trim().toLowerCase()))}catch{return!1}}function jt(e,t){return{getIsGroup:Ot,getIgnored:kt,getKey(t){return Ot(t)?t.name||t.key||`key-required`:t[e]},getChildren(e){return e[t]}}}function Mt(e,t,n,r){if(!t)return e;function i(e){if(!Array.isArray(e))return[];let a=[];for(let o of e)if(Ot(o)){let e=i(o[r]);e.length&&a.push(Object.assign({},o,{[r]:e}))}else if(kt(o))continue;else t(n,o)&&a.push(o);return a}return i(e)}function Nt(e,t,n){let r=new Map;return e.forEach(e=>{Ot(e)?e[n].forEach(e=>{r.set(e[t],e)}):r.set(e[t],e)}),r}var Pt=U([G(`select`,`
 z-index: auto;
 outline: none;
 width: 100%;
 position: relative;
 font-weight: var(--n-font-weight);
 `),G(`select-menu`,`
 margin: 4px 0;
 box-shadow: var(--n-menu-box-shadow);
 `,[j({originalTransition:`background-color .3s var(--n-bezier), box-shadow .3s var(--n-bezier)`})])]),Ft=Z({name:`Select`,props:Object.assign(Object.assign({},H.props),{to:a.propTo,bordered:{type:Boolean,default:void 0},clearable:Boolean,clearCreatedOptionsOnClear:{type:Boolean,default:!0},clearFilterAfterSelect:{type:Boolean,default:!0},options:{type:Array,default:()=>[]},defaultValue:{type:[String,Number,Array],default:null},keyboard:{type:Boolean,default:!0},value:[String,Number,Array],placeholder:String,menuProps:Object,multiple:Boolean,size:String,menuSize:{type:String},filterable:Boolean,disabled:{type:Boolean,default:void 0},remote:Boolean,loading:Boolean,filter:Function,placement:{type:String,default:`bottom-start`},widthMode:{type:String,default:`trigger`},tag:Boolean,onCreate:Function,fallbackOption:{type:[Function,Boolean],default:void 0},show:{type:Boolean,default:void 0},showArrow:{type:Boolean,default:!0},maxTagCount:[Number,String],ellipsisTagPopoverProps:Object,consistentMenuWidth:{type:Boolean,default:!0},virtualScroll:{type:Boolean,default:!0},labelField:{type:String,default:`label`},valueField:{type:String,default:`value`},childrenField:{type:String,default:`children`},renderLabel:Function,renderOption:Function,renderTag:Function,"onUpdate:value":[Function,Array],inputProps:Object,nodeProps:Function,ignoreComposition:{type:Boolean,default:!0},showOnFocus:Boolean,onUpdateValue:[Function,Array],onBlur:[Function,Array],onClear:[Function,Array],onFocus:[Function,Array],onScroll:[Function,Array],onSearch:[Function,Array],onUpdateShow:[Function,Array],"onUpdate:show":[Function,Array],displayDirective:{type:String,default:`show`},resetMenuOnOptionsChange:{type:Boolean,default:!0},status:String,showCheckmark:{type:Boolean,default:!0},scrollbarProps:Object,onChange:[Function,Array],items:Array}),slots:Object,setup(e){let{mergedClsPrefixRef:t,mergedBorderedRef:r,namespaceRef:o,inlineThemeDisabled:s,mergedComponentPropsRef:c}=ye(e),l=H(`Select`,`-select`,Pt,be,e,t),u=W(e.defaultValue),f=i(R(e,`value`),u),p=W(!1),m=W(``),_=re(e,[`items`,`options`]),v=W([]),y=W([]),b=N(()=>y.value.concat(v.value).concat(_.value)),x=N(()=>{let{filter:t}=e;if(t)return t;let{labelField:n,valueField:r}=e;return(e,t)=>{if(!t)return!1;let i=t[n];if(typeof i==`string`)return At(e,i);let a=t[r];return typeof a==`string`?At(e,a):typeof a==`number`?At(e,String(a)):!1}}),S=N(()=>{if(e.remote)return _.value;{let{value:t}=b,{value:n}=m;return!n.length||!e.filterable?t:Mt(t,x.value,n,e.childrenField)}}),w=N(()=>{let{valueField:t,childrenField:n}=e,r=jt(t,n);return dt(S.value,r)}),T=N(()=>Nt(b.value,e.valueField,e.childrenField)),D=W(!1),O=i(R(e,`show`),D),k=W(null),te=W(null),j=W(null),{localeRef:M}=ee(`Select`),ne=N(()=>e.placeholder??M.value.placeholder),P=[],F=W(new Map),ie=N(()=>{let{fallbackOption:t}=e;if(t===void 0){let{labelField:t,valueField:n}=e;return e=>({[t]:String(e),[n]:e})}return t===!1?!1:e=>Object.assign(t(e),{value:e})});function I(t){let n=e.remote,{value:r}=F,{value:i}=T,{value:a}=ie,o=[];return t.forEach(e=>{if(i.has(e))o.push(i.get(e));else if(n&&r.has(e))o.push(r.get(e));else if(a){let t=a(e);t&&o.push(t)}}),o}let ae=N(()=>{if(e.multiple){let{value:e}=f;return Array.isArray(e)?I(e):[]}return null}),oe=N(()=>{let{value:t}=f;return!e.multiple&&!Array.isArray(t)?t===null?null:I([t])[0]||null:null}),L=h(e,{mergedSize:t=>{let{size:n}=e;if(n)return n;let{mergedSize:r}=t||{};return r?.value?r.value:c?.value?.Select?.size||`medium`}}),{mergedSizeRef:z,mergedDisabledRef:B,mergedStatusRef:V}=L;function U(t,n){let{onChange:r,"onUpdate:value":i,onUpdateValue:a}=e,{nTriggerFormChange:o,nTriggerFormInput:s}=L;r&&d(r,t,n),a&&d(a,t,n),i&&d(i,t,n),u.value=t,o(),s()}function G(t){let{onBlur:n}=e,{nTriggerFormBlur:r}=L;n&&d(n,t),r()}function se(){let{onClear:t}=e;t&&d(t)}function ce(t){let{onFocus:n,showOnFocus:r}=e,{nTriggerFormFocus:i}=L;n&&d(n,t),i(),r&&J()}function K(t){let{onSearch:n}=e;n&&d(n,t)}function q(t){let{onScroll:n}=e;n&&d(n,t)}function le(){var t;let{remote:n,multiple:r}=e;if(n){let{value:n}=F;if(r){let{valueField:r}=e;(t=ae.value)==null||t.forEach(e=>{n.set(e[r],e)})}else{let t=oe.value;t&&n.set(t[e.valueField],t)}}}function de(t){let{onUpdateShow:n,"onUpdate:show":r}=e;n&&d(n,t),r&&d(r,t),D.value=t}function J(){B.value||(de(!0),D.value=!0,e.filterable&&je())}function Y(){de(!1)}function fe(){m.value=``,y.value=P}let X=W(!1);function pe(){e.filterable&&(X.value=!0)}function me(){e.filterable&&(X.value=!1,O.value||fe())}function he(){B.value||(O.value?e.filterable?je():Y():J())}function ge(e){(j.value?.selfRef)?.contains(e.relatedTarget)||(p.value=!1,G(e),Y())}function Z(e){ce(e),p.value=!0}function _e(){p.value=!0}function ve(e){k.value?.$el.contains(e.relatedTarget)||(p.value=!1,G(e),Y())}function Q(){var e;(e=k.value)==null||e.focus(),Y()}function xe(e){O.value&&(k.value?.$el.contains(g(e))||Y())}function Se(t){if(!Array.isArray(t))return[];if(ie.value)return Array.from(t);{let{remote:n}=e,{value:r}=T;if(n){let{value:e}=F;return t.filter(t=>r.has(t)||e.has(t))}else return t.filter(e=>r.has(e))}}function Ce(e){we(e.rawNode)}function we(t){if(B.value)return;let{tag:n,remote:r,clearFilterAfterSelect:i,valueField:a}=e;if(n&&!r){let{value:e}=y,t=e[0]||null;if(t){let e=v.value;e.length?e.push(t):v.value=[t],y.value=P}}if(r&&F.value.set(t[a],t),e.multiple){let e=Se(f.value),o=e.findIndex(e=>e===t[a]);if(~o){if(e.splice(o,1),n&&!r){let e=Te(t[a]);~e&&(v.value.splice(e,1),i&&(m.value=``))}}else e.push(t[a]),i&&(m.value=``);U(e,I(e))}else{if(n&&!r){let e=Te(t[a]);~e?v.value=[v.value[e]]:v.value=P}Ae(),Y(),U(t[a],t)}}function Te(t){return v.value.findIndex(n=>n[e.valueField]===t)}function $(t){O.value||J();let{value:n}=t.target;m.value=n;let{tag:r,remote:i}=e;if(K(n),r&&!i){if(!n){y.value=P;return}let{onCreate:t}=e,r=t?t(n):{[e.labelField]:n,[e.valueField]:n},{valueField:i,labelField:a}=e;_.value.some(e=>e[i]===r[i]||e[a]===r[a])||v.value.some(e=>e[i]===r[i]||e[a]===r[a])?y.value=P:y.value=[r]}}function Ee(t){t.stopPropagation();let{multiple:n,tag:r,remote:i,clearCreatedOptionsOnClear:a}=e;!n&&e.filterable&&Y(),r&&!i&&a&&(v.value=P),se(),n?U([],[]):U(null,null)}function De(e){!A(e,`action`)&&!A(e,`empty`)&&!A(e,`header`)&&e.preventDefault()}function Oe(e){q(e)}function ke(t){var n,r,i;if(!e.keyboard){t.preventDefault();return}switch(t.key){case` `:if(e.filterable)break;t.preventDefault();case`Enter`:if(!k.value?.isComposing){if(O.value){let t=j.value?.getPendingTmNode();t?Ce(t):e.filterable||(Y(),Ae())}else if(J(),e.tag&&X.value){let t=y.value[0];if(t){let n=t[e.valueField],{value:r}=f;e.multiple&&Array.isArray(r)&&r.includes(n)||we(t)}}}t.preventDefault();break;case`ArrowUp`:if(t.preventDefault(),e.loading)return;O.value&&((n=j.value)==null||n.prev());break;case`ArrowDown`:if(t.preventDefault(),e.loading)return;O.value?(r=j.value)==null||r.next():J();break;case`Escape`:O.value&&(E(t),Y()),(i=k.value)==null||i.focus();break}}function Ae(){var e;(e=k.value)==null||e.focus()}function je(){var e;(e=k.value)==null||e.focusInput()}function Me(){var e;O.value&&((e=te.value)==null||e.syncPosition())}le(),ue(R(e,`options`),le);let Ne={focus:()=>{var e;(e=k.value)==null||e.focus()},focusInput:()=>{var e;(e=k.value)==null||e.focusInput()},blur:()=>{var e;(e=k.value)==null||e.blur()},blurInput:()=>{var e;(e=k.value)==null||e.blurInput()}},Pe=N(()=>{let{self:{menuBoxShadow:e}}=l.value;return{"--n-menu-box-shadow":e}}),Fe=s?C(`select`,void 0,Pe,e):void 0;return Object.assign(Object.assign({},Ne),{mergedStatus:V,mergedClsPrefix:t,mergedBordered:r,namespace:o,treeMate:w,isMounted:n(),triggerRef:k,menuRef:j,pattern:m,uncontrolledShow:D,mergedShow:O,adjustedTo:a(e),uncontrolledValue:u,mergedValue:f,followerRef:te,localizedPlaceholder:ne,selectedOption:oe,selectedOptions:ae,mergedSize:z,mergedDisabled:B,focused:p,activeWithoutMenuOpen:X,inlineThemeDisabled:s,onTriggerInputFocus:pe,onTriggerInputBlur:me,handleTriggerOrMenuResize:Me,handleMenuFocus:_e,handleMenuBlur:ve,handleMenuTabOut:Q,handleTriggerClick:he,handleToggle:Ce,handleDeleteOption:we,handlePatternInput:$,handleClear:Ee,handleTriggerBlur:ge,handleTriggerFocus:Z,handleKeydown:ke,handleMenuAfterLeave:fe,handleMenuClickOutside:xe,handleMenuScroll:Oe,handleMenuKeydown:ke,handleMenuMousedown:De,mergedTheme:l,cssVars:s?void 0:Pe,themeClass:Fe?.themeClass,onRender:Fe?.onRender})},render(){return X(`div`,{class:`${this.mergedClsPrefix}-select`},X(r,null,{default:()=>[X(t,null,{default:()=>X(Dt,{ref:`triggerRef`,inlineThemeDisabled:this.inlineThemeDisabled,status:this.mergedStatus,inputProps:this.inputProps,clsPrefix:this.mergedClsPrefix,showArrow:this.showArrow,maxTagCount:this.maxTagCount,ellipsisTagPopoverProps:this.ellipsisTagPopoverProps,bordered:this.mergedBordered,active:this.activeWithoutMenuOpen||this.mergedShow,pattern:this.pattern,placeholder:this.localizedPlaceholder,selectedOption:this.selectedOption,selectedOptions:this.selectedOptions,multiple:this.multiple,renderTag:this.renderTag,renderLabel:this.renderLabel,filterable:this.filterable,clearable:this.clearable,disabled:this.mergedDisabled,size:this.mergedSize,theme:this.mergedTheme.peers.InternalSelection,labelField:this.labelField,valueField:this.valueField,themeOverrides:this.mergedTheme.peerOverrides.InternalSelection,loading:this.loading,focused:this.focused,onClick:this.handleTriggerClick,onDeleteOption:this.handleDeleteOption,onPatternInput:this.handlePatternInput,onClear:this.handleClear,onBlur:this.handleTriggerBlur,onFocus:this.handleTriggerFocus,onKeydown:this.handleKeydown,onPatternBlur:this.onTriggerInputBlur,onPatternFocus:this.onTriggerInputFocus,onResize:this.handleTriggerOrMenuResize,ignoreComposition:this.ignoreComposition},{arrow:()=>{var e;return[(e=this.$slots).arrow?.call(e)]}})}),X(y,{ref:`followerRef`,show:this.mergedShow,to:this.adjustedTo,teleportDisabled:this.adjustedTo===a.tdkey,containerClass:this.namespace,width:this.consistentMenuWidth?`target`:void 0,minWidth:`target`,placement:this.placement},{default:()=>X(J,{name:`fade-in-scale-up-transition`,appear:this.isMounted,onAfterLeave:this.handleMenuAfterLeave},{default:()=>{var e;return this.mergedShow||this.displayDirective===`show`?((e=this.onRender)==null||e.call(this),ce(X(vt,Object.assign({},this.menuProps,{ref:`menuRef`,onResize:this.handleTriggerOrMenuResize,inlineThemeDisabled:this.inlineThemeDisabled,virtualScroll:this.consistentMenuWidth&&this.virtualScroll,class:[`${this.mergedClsPrefix}-select-menu`,this.themeClass,this.menuProps?.class],clsPrefix:this.mergedClsPrefix,focusable:!0,labelField:this.labelField,valueField:this.valueField,autoPending:!0,nodeProps:this.nodeProps,theme:this.mergedTheme.peers.InternalSelectMenu,themeOverrides:this.mergedTheme.peerOverrides.InternalSelectMenu,treeMate:this.treeMate,multiple:this.multiple,size:this.menuSize,renderOption:this.renderOption,renderLabel:this.renderLabel,value:this.mergedValue,style:[this.menuProps?.style,this.cssVars],onToggle:this.handleToggle,onScroll:this.handleMenuScroll,onFocus:this.handleMenuFocus,onBlur:this.handleMenuBlur,onKeydown:this.handleMenuKeydown,onTabOut:this.handleMenuTabOut,onMousedown:this.handleMenuMousedown,show:this.mergedShow,showCheckmark:this.showCheckmark,resetMenuOnOptionsChange:this.resetMenuOnOptionsChange,scrollbarProps:this.scrollbarProps}),{empty:()=>{var e;return[(e=this.$slots).empty?.call(e)]},header:()=>{var e;return[(e=this.$slots).header?.call(e)]},action:()=>{var e;return[(e=this.$slots).action?.call(e)]}}),this.displayDirective===`show`?[[B,this.mergedShow],[c,this.handleMenuClickOutside,void 0,{capture:!0}]]:[[c,this.handleMenuClickOutside,void 0,{capture:!0}]])):null}})})]}))}});export{Ae as n,$ as r,Ft as t};
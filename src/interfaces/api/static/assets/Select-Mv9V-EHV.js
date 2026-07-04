import{A as e,B as t,C as n,D as r,F as i,H as a,I as o,J as s,L as c,M as l,N as u,R as d,T as f,U as p,V as m,X as h,Y as g,_,a as v,et as y,g as b,h as x,j as S,k as C,l as w,nt as ee,o as T,p as E,q as D,rt as O,s as k,tt as A,u as te,v as ne,w as j}from"./ErrorBanner-CV9KX4CB.js";import{a as re,n as ie}from"./GlossaryTip-D1a-jSlW.js";import{Ct as M,Et as N,Ht as P,Mt as F,Pt as I,Qt as L,Rt as ae,Sn as R,Tn as z,Tt as B,Yt as V,Zt as H,_ as oe,_n as U,_t as W,bt as G,fn as se,g as ce,gt as le,hn as ue,ht as de,in as K,l as fe,m as q,mn as J,mt as pe,on as Y,p as me,qt as he,tn as ge,un as _e,ut as ve,wt as X,x as Z,xt as Q,y as ye}from"./index-fjOoYR_E.js";var $=`v-hidden`,be=c(`[v-hidden]`,{display:`none!important`}),xe=V({name:`Overflow`,props:{getCounter:Function,getTail:Function,updateCounter:Function,onUpdateCount:Function,onUpdateOverflow:Function},setup(e,{slots:t}){let n=R(null),r=R(null);function i(i){let{value:a}=n,{getCounter:o,getTail:s}=e,c;if(c=o===void 0?r.value:o(),!a||!c)return;c.hasAttribute($)&&c.removeAttribute($);let{children:l}=a;if(i.showAllItemsBeforeCalculate)for(let e of l)e.hasAttribute($)&&e.removeAttribute($);let u=a.offsetWidth,d=[],f=t.tail?s?.():null,p=f?f.offsetWidth:0,m=!1,h=a.children.length-+!!t.tail;for(let t=0;t<h-1;++t){if(t<0)continue;let n=l[t];if(m){n.hasAttribute($)||n.setAttribute($,``);continue}else n.hasAttribute($)&&n.removeAttribute($);let r=n.offsetWidth;if(p+=r,d[t]=r,p>u){let{updateCounter:n}=e;for(let r=t;r>=0;--r){let i=h-1-r;n===void 0?c.textContent=`${i}`:n(i);let a=c.offsetWidth;if(p-=d[r],p+a<=u||r===0){m=!0,t=r-1,f&&(t===-1?(f.style.maxWidth=`${u-a}px`,f.style.boxSizing=`border-box`):f.style.maxWidth=``);let{onUpdateCount:n}=e;n&&n(i);break}}}}let{onUpdateOverflow:g}=e;m?g!==void 0&&g(!0):(g!==void 0&&g(!1),c.setAttribute($,``))}let a=pe();return be.mount({id:`vueuc/overflow`,head:!0,anchorMetaName:d,ssr:a}),Y(()=>i({showAllItemsBeforeCalculate:!1})),{selfRef:n,counterRef:r,sync:i}},render(){let{$slots:e}=this;return ge(()=>this.sync({showAllItemsBeforeCalculate:!1})),H(`div`,{class:`v-overflow`,ref:`selfRef`},[se(e,`default`),e.counter?e.counter():H(`span`,{style:{display:`inline-block`},ref:`counterRef`}),e.tail?e.tail():null])}});function Se(e,t){t&&(Y(()=>{let{value:n}=e;n&&i.registerHandler(n,t)}),J(e,(e,t)=>{t&&i.unregisterHandler(t)},{deep:!1}),K(()=>{let{value:t}=e;t&&i.unregisterHandler(t)}))}function Ce(e){switch(typeof e){case`string`:return e||void 0;case`number`:return String(e);default:return}}function we(e){let t=e.filter(e=>e!==void 0);if(t.length!==0)return t.length===1?t[0]:t=>{e.forEach(e=>{e&&e(t)})}}function Te(e,...t){return typeof e==`function`?e(...t):typeof e==`string`?he(e):typeof e==`number`?he(String(e)):null}var Ee=V({name:`Checkmark`,render(){return H(`svg`,{xmlns:`http://www.w3.org/2000/svg`,viewBox:`0 0 16 16`},H(`g`,{fill:`none`},H(`path`,{d:`M14.046 3.486a.75.75 0 0 1-.032 1.06l-7.93 7.474a.85.85 0 0 1-1.188-.022l-2.68-2.72a.75.75 0 1 1 1.068-1.053l2.234 2.267l7.468-7.038a.75.75 0 0 1 1.06.032z`,fill:`currentColor`})))}}),De=E(`close`,()=>H(`svg`,{viewBox:`0 0 12 12`,version:`1.1`,xmlns:`http://www.w3.org/2000/svg`,"aria-hidden":!0},H(`g`,{stroke:`none`,"stroke-width":`1`,fill:`none`,"fill-rule":`evenodd`},H(`g`,{fill:`currentColor`,"fill-rule":`nonzero`},H(`path`,{d:`M2.08859116,2.2156945 L2.14644661,2.14644661 C2.32001296,1.97288026 2.58943736,1.95359511 2.7843055,2.08859116 L2.85355339,2.14644661 L6,5.293 L9.14644661,2.14644661 C9.34170876,1.95118446 9.65829124,1.95118446 9.85355339,2.14644661 C10.0488155,2.34170876 10.0488155,2.65829124 9.85355339,2.85355339 L6.707,6 L9.85355339,9.14644661 C10.0271197,9.32001296 10.0464049,9.58943736 9.91140884,9.7843055 L9.85355339,9.85355339 C9.67998704,10.0271197 9.41056264,10.0464049 9.2156945,9.91140884 L9.14644661,9.85355339 L6,6.707 L2.85355339,9.85355339 C2.65829124,10.0488155 2.34170876,10.0488155 2.14644661,9.85355339 C1.95118446,9.65829124 1.95118446,9.34170876 2.14644661,9.14644661 L5.293,6 L2.14644661,2.85355339 C1.97288026,2.67998704 1.95359511,2.41056264 2.08859116,2.2156945 L2.14644661,2.14644661 L2.08859116,2.2156945 Z`}))))),Oe=V({name:`Empty`,render(){return H(`svg`,{viewBox:`0 0 28 28`,fill:`none`,xmlns:`http://www.w3.org/2000/svg`},H(`path`,{d:`M26 7.5C26 11.0899 23.0899 14 19.5 14C15.9101 14 13 11.0899 13 7.5C13 3.91015 15.9101 1 19.5 1C23.0899 1 26 3.91015 26 7.5ZM16.8536 4.14645C16.6583 3.95118 16.3417 3.95118 16.1464 4.14645C15.9512 4.34171 15.9512 4.65829 16.1464 4.85355L18.7929 7.5L16.1464 10.1464C15.9512 10.3417 15.9512 10.6583 16.1464 10.8536C16.3417 11.0488 16.6583 11.0488 16.8536 10.8536L19.5 8.20711L22.1464 10.8536C22.3417 11.0488 22.6583 11.0488 22.8536 10.8536C23.0488 10.6583 23.0488 10.3417 22.8536 10.1464L20.2071 7.5L22.8536 4.85355C23.0488 4.65829 23.0488 4.34171 22.8536 4.14645C22.6583 3.95118 22.3417 3.95118 22.1464 4.14645L19.5 6.79289L16.8536 4.14645Z`,fill:`currentColor`}),H(`path`,{d:`M25 22.75V12.5991C24.5572 13.0765 24.053 13.4961 23.5 13.8454V16H17.5L17.3982 16.0068C17.0322 16.0565 16.75 16.3703 16.75 16.75C16.75 18.2688 15.5188 19.5 14 19.5C12.4812 19.5 11.25 18.2688 11.25 16.75L11.2432 16.6482C11.1935 16.2822 10.8797 16 10.5 16H4.5V7.25C4.5 6.2835 5.2835 5.5 6.25 5.5H12.2696C12.4146 4.97463 12.6153 4.47237 12.865 4H6.25C4.45507 4 3 5.45507 3 7.25V22.75C3 24.5449 4.45507 26 6.25 26H21.75C23.5449 26 25 24.5449 25 22.75ZM4.5 22.75V17.5H9.81597L9.85751 17.7041C10.2905 19.5919 11.9808 21 14 21L14.215 20.9947C16.2095 20.8953 17.842 19.4209 18.184 17.5H23.5V22.75C23.5 23.7165 22.7165 24.5 21.75 24.5H6.25C5.2835 24.5 4.5 23.7165 4.5 22.75Z`,fill:`currentColor`}))}}),ke=Q(`base-close`,`
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
`,[X(`absolute`,`
 height: var(--n-close-icon-size);
 width: var(--n-close-icon-size);
 `),G(`&::before`,`
 content: "";
 position: absolute;
 width: var(--n-close-size);
 height: var(--n-close-size);
 left: 50%;
 top: 50%;
 transform: translateY(-50%) translateX(-50%);
 transition: inherit;
 border-radius: inherit;
 `),B(`disabled`,[G(`&:hover`,`
 color: var(--n-close-icon-color-hover);
 `),G(`&:hover::before`,`
 background-color: var(--n-close-color-hover);
 `),G(`&:focus::before`,`
 background-color: var(--n-close-color-hover);
 `),G(`&:active`,`
 color: var(--n-close-icon-color-pressed);
 `),G(`&:active::before`,`
 background-color: var(--n-close-color-pressed);
 `)]),X(`disabled`,`
 cursor: not-allowed;
 color: var(--n-close-icon-color-disabled);
 background-color: transparent;
 `),X(`round`,[G(`&::before`,`
 border-radius: 50%;
 `)])]),Ae=V({name:`BaseClose`,props:{isButtonTag:{type:Boolean,default:!0},clsPrefix:{type:String,required:!0},disabled:{type:Boolean,default:void 0},focusable:{type:Boolean,default:!0},round:Boolean,onClick:Function,absolute:Boolean},setup(e){return b(`-base-close`,ke,z(e,`clsPrefix`)),()=>{let{clsPrefix:t,disabled:n,absolute:r,round:i,isButtonTag:a}=e;return H(a?`button`:`div`,{type:a?`button`:void 0,tabindex:n||!e.focusable?-1:0,"aria-disabled":n,"aria-label":`close`,role:a?void 0:`button`,disabled:n,class:[`${t}-base-close`,r&&`${t}-base-close--absolute`,n&&`${t}-base-close--disabled`,i&&`${t}-base-close--round`],onMousedown:t=>{e.focusable||t.preventDefault()},onClick:e.onClick},H(x,{clsPrefix:t},{default:()=>H(De,null)}))}}});function je(e){return Array.isArray(e)?e:[e]}var Me={STOP:`STOP`};function Ne(e,t){let n=t(e);e.children!==void 0&&n!==Me.STOP&&e.children.forEach(e=>Ne(e,t))}function Pe(e,t={}){let{preserveGroup:n=!1}=t,r=[],i=n?e=>{e.isLeaf||(r.push(e.key),a(e.children))}:e=>{e.isLeaf||(e.isGroup||r.push(e.key),a(e.children))};function a(e){e.forEach(i)}return a(e),r}function Fe(e,t){let{isLeaf:n}=e;return n===void 0?!t(e):n}function Ie(e){return e.children}function Le(e){return e.key}function Re(){return!1}function ze(e,t){let{isLeaf:n}=e;return!(n===!1&&!Array.isArray(t(e)))}function Be(e){return e.disabled===!0}function Ve(e,t){return e.isLeaf===!1&&!Array.isArray(t(e))}function He(e){return e==null?[]:Array.isArray(e)?e:e.checkedKeys??[]}function Ue(e){return e==null||Array.isArray(e)?[]:e.indeterminateKeys??[]}function We(e,t){let n=new Set(e);return t.forEach(e=>{n.has(e)||n.add(e)}),Array.from(n)}function Ge(e,t){let n=new Set(e);return t.forEach(e=>{n.has(e)&&n.delete(e)}),Array.from(n)}function Ke(e){return e?.type===`group`}function qe(e){let t=new Map;return e.forEach((e,n)=>{t.set(e.key,n)}),e=>t.get(e)??null}var Je=class extends Error{constructor(){super(),this.message=`SubtreeNotLoadedError: checking a subtree whose required nodes are not fully loaded.`}};function Ye(e,t,n,r){return $e(t.concat(e),n,r,!1)}function Xe(e,t){let n=new Set;return e.forEach(e=>{let r=t.treeNodeMap.get(e);if(r!==void 0){let e=r.parent;for(;e!==null&&!(e.disabled||n.has(e.key));)n.add(e.key),e=e.parent}}),n}function Ze(e,t,n,r){let i=$e(t,n,r,!1),a=$e(e,n,r,!0),o=Xe(e,n),s=[];return i.forEach(e=>{(a.has(e)||o.has(e))&&s.push(e)}),s.forEach(e=>i.delete(e)),i}function Qe(e,t){let{checkedKeys:n,keysToCheck:r,keysToUncheck:i,indeterminateKeys:a,cascade:o,leafOnly:s,checkStrategy:c,allowNotLoaded:l}=e;if(!o)return r===void 0?i===void 0?{checkedKeys:Array.from(n),indeterminateKeys:Array.from(a)}:{checkedKeys:Ge(n,i),indeterminateKeys:Array.from(a)}:{checkedKeys:We(n,r),indeterminateKeys:Array.from(a)};let{levelTreeNodeMap:u}=t,d;d=i===void 0?r===void 0?$e(n,t,l,!1):Ye(r,n,t,l):Ze(i,n,t,l);let f=c===`parent`,p=c===`child`||s,m=d,h=new Set,g=Math.max.apply(null,Array.from(u.keys()));for(let e=g;e>=0;--e){let t=e===0,n=u.get(e);for(let e of n){if(e.isLeaf)continue;let{key:n,shallowLoaded:r}=e;if(p&&r&&e.children.forEach(e=>{!e.disabled&&!e.isLeaf&&e.shallowLoaded&&m.has(e.key)&&m.delete(e.key)}),e.disabled||!r)continue;let i=!0,a=!1,o=!0;for(let t of e.children){let e=t.key;if(!t.disabled){if(o&&=!1,m.has(e))a=!0;else if(h.has(e)){a=!0,i=!1;break}else if(i=!1,a)break}}i&&!o?(f&&e.children.forEach(e=>{!e.disabled&&m.has(e.key)&&m.delete(e.key)}),m.add(n)):a&&h.add(n),t&&p&&m.has(n)&&m.delete(n)}}return{checkedKeys:Array.from(m),indeterminateKeys:Array.from(h)}}function $e(e,t,n,r){let{treeNodeMap:i,getChildren:a}=t,o=new Set,s=new Set(e);return e.forEach(e=>{let t=i.get(e);t!==void 0&&Ne(t,e=>{if(e.disabled)return Me.STOP;let{key:t}=e;if(!o.has(t)&&(o.add(t),s.add(t),Ve(e.rawNode,a))){if(r)return Me.STOP;if(!n)throw new Je}})}),s}function et(e,{includeGroup:t=!1,includeSelf:n=!0},r){let i=r.treeNodeMap,a=e==null?null:i.get(e)??null,o={keyPath:[],treeNodePath:[],treeNode:a};if(a?.ignored)return o.treeNode=null,o;for(;a;)!a.ignored&&(t||!a.isGroup)&&o.treeNodePath.push(a),a=a.parent;return o.treeNodePath.reverse(),n||o.treeNodePath.pop(),o.keyPath=o.treeNodePath.map(e=>e.key),o}function tt(e){if(e.length===0)return null;let t=e[0];return t.isGroup||t.ignored||t.disabled?t.getNext():t}function nt(e,t){let n=e.siblings,r=n.length,{index:i}=e;return t?n[(i+1)%r]:i===n.length-1?null:n[i+1]}function rt(e,t,{loop:n=!1,includeDisabled:r=!1}={}){let i=t===`prev`?it:nt,a={reverse:t===`prev`},o=!1,s=null;function c(t){if(t!==null){if(t===e){if(!o)o=!0;else if(!e.disabled&&!e.isGroup){s=e;return}}else if((!t.disabled||r)&&!t.ignored&&!t.isGroup){s=t;return}if(t.isGroup){let e=ot(t,a);e===null?c(i(t,n)):s=e}else{let e=i(t,!1);if(e!==null)c(e);else{let e=at(t);e?.isGroup?c(i(e,n)):n&&c(i(t,!0))}}}}return c(e),s}function it(e,t){let n=e.siblings,r=n.length,{index:i}=e;return t?n[(i-1+r)%r]:i===0?null:n[i-1]}function at(e){return e.parent}function ot(e,t={}){let{reverse:n=!1}=t,{children:r}=e;if(r){let{length:e}=r,i=n?e-1:0,a=n?-1:e,o=n?-1:1;for(let e=i;e!==a;e+=o){let n=r[e];if(!n.disabled&&!n.ignored)if(n.isGroup){let e=ot(n,t);if(e!==null)return e}else return n}}return null}var st={getChild(){return this.ignored?null:ot(this)},getParent(){let{parent:e}=this;return e?.isGroup?e.getParent():e},getNext(e={}){return rt(this,`next`,e)},getPrev(e={}){return rt(this,`prev`,e)}};function ct(e,t){let n=t?new Set(t):void 0,r=[];function i(e){e.forEach(e=>{r.push(e),!(e.isLeaf||!e.children||e.ignored)&&(e.isGroup||n===void 0||n.has(e.key))&&i(e.children)})}return i(e),r}function lt(e,t){let n=e.key;for(;t;){if(t.key===n)return!0;t=t.parent}return!1}function ut(e,t,n,r,i,a=null,o=0){let s=[];return e.forEach((c,l)=>{var u;let d=Object.create(r);if(d.rawNode=c,d.siblings=s,d.level=o,d.index=l,d.isFirstChild=l===0,d.isLastChild=l+1===e.length,d.parent=a,!d.ignored){let e=i(c);Array.isArray(e)&&(d.children=ut(e,t,n,r,i,d,o+1))}s.push(d),t.set(d.key,d),n.has(o)||n.set(o,[]),(u=n.get(o))==null||u.push(d)}),s}function dt(e,t={}){let n=new Map,r=new Map,{getDisabled:i=Be,getIgnored:a=Re,getIsGroup:o=Ke,getKey:s=Le}=t,c=t.getChildren??Ie,l=t.ignoreEmptyChildren?e=>{let t=c(e);return Array.isArray(t)?t.length?t:null:t}:c,u=ut(e,n,r,Object.assign({get key(){return s(this.rawNode)},get disabled(){return i(this.rawNode)},get isGroup(){return o(this.rawNode)},get isLeaf(){return Fe(this.rawNode,l)},get shallowLoaded(){return ze(this.rawNode,l)},get ignored(){return a(this.rawNode)},contains(e){return lt(this,e)}},st),l);function d(e){if(e==null)return null;let t=n.get(e);return t&&!t.isGroup&&!t.ignored?t:null}function f(e){if(e==null)return null;let t=n.get(e);return t&&!t.ignored?t:null}function p(e,t){let n=f(e);return n?n.getPrev(t):null}function m(e,t){let n=f(e);return n?n.getNext(t):null}function h(e){let t=f(e);return t?t.getParent():null}function g(e){let t=f(e);return t?t.getChild():null}let _={treeNodes:u,treeNodeMap:n,levelTreeNodeMap:r,maxLevel:Math.max(...r.keys()),getChildren:l,getFlattenedNodes(e){return ct(u,e)},getNode:d,getPrev:p,getNext:m,getParent:h,getChild:g,getFirstAvailableNode(){return tt(u)},getPath(e,t={}){return et(e,t,_)},getCheckedKeys(e,t={}){let{cascade:n=!0,leafOnly:r=!1,checkStrategy:i=`all`,allowNotLoaded:a=!1}=t;return Qe({checkedKeys:He(e),indeterminateKeys:Ue(e),cascade:n,leafOnly:r,checkStrategy:i,allowNotLoaded:a},_)},check(e,t,n={}){let{cascade:r=!0,leafOnly:i=!1,checkStrategy:a=`all`,allowNotLoaded:o=!1}=n;return Qe({checkedKeys:He(t),indeterminateKeys:Ue(t),keysToCheck:e==null?[]:je(e),cascade:r,leafOnly:i,checkStrategy:a,allowNotLoaded:o},_)},uncheck(e,t,n={}){let{cascade:r=!0,leafOnly:i=!1,checkStrategy:a=`all`,allowNotLoaded:o=!1}=n;return Qe({checkedKeys:He(t),indeterminateKeys:Ue(t),keysToUncheck:e==null?[]:je(e),cascade:r,leafOnly:i,checkStrategy:a,allowNotLoaded:o},_)},getNonLeafKeys(e={}){return Pe(u,e)}};return _}var ft=Q(`empty`,`
 display: flex;
 flex-direction: column;
 align-items: center;
 font-size: var(--n-font-size);
`,[M(`icon`,`
 width: var(--n-icon-size);
 height: var(--n-icon-size);
 font-size: var(--n-icon-size);
 line-height: var(--n-icon-size);
 color: var(--n-icon-color);
 transition:
 color .3s var(--n-bezier);
 `,[G(`+`,[M(`description`,`
 margin-top: 8px;
 `)])]),M(`description`,`
 transition: color .3s var(--n-bezier);
 color: var(--n-text-color);
 `),M(`extra`,`
 text-align: center;
 transition: color .3s var(--n-bezier);
 margin-top: 12px;
 color: var(--n-extra-text-color);
 `)]),pt=V({name:`Empty`,props:Object.assign(Object.assign({},Z.props),{description:String,showDescription:{type:Boolean,default:!0},showIcon:{type:Boolean,default:!0},size:{type:String,default:`medium`},renderIcon:Function}),slots:Object,setup(e){let{mergedClsPrefixRef:t,inlineThemeDisabled:n,mergedComponentPropsRef:r}=ve(e),i=Z(`Empty`,`-empty`,ft,oe,e,t),{localeRef:a}=ne(`Empty`),o=P(()=>e.description??r?.value?.Empty?.description),s=P(()=>r?.value?.Empty?.renderIcon||(()=>H(Oe,null))),c=P(()=>{let{size:t}=e,{common:{cubicBezierEaseInOut:n},self:{[N(`iconSize`,t)]:r,[N(`fontSize`,t)]:a,textColor:o,iconColor:s,extraTextColor:c}}=i.value;return{"--n-icon-size":r,"--n-font-size":a,"--n-bezier":n,"--n-text-color":o,"--n-icon-color":s,"--n-extra-text-color":c}}),l=n?j(`empty`,P(()=>{let t=``,{size:n}=e;return t+=n[0],t}),c,e):void 0;return{mergedClsPrefix:t,mergedRenderIcon:s,localizedDescription:P(()=>o.value||a.value.description),cssVars:n?void 0:c,themeClass:l?.themeClass,onRender:l?.onRender}},render(){let{$slots:e,mergedClsPrefix:t,onRender:n}=this;return n?.(),H(`div`,{class:[`${t}-empty`,this.themeClass],style:this.cssVars},this.showIcon?H(`div`,{class:`${t}-empty__icon`},e.icon?e.icon():H(x,{clsPrefix:t},{default:this.mergedRenderIcon})):null,this.showDescription?H(`div`,{class:`${t}-empty__description`},e.default?e.default():this.localizedDescription):null,e.extra?H(`div`,{class:`${t}-empty__extra`},e.extra()):null)}}),mt=V({name:`NBaseSelectGroupHeader`,props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(){let{renderLabelRef:e,renderOptionRef:t,labelFieldRef:n,nodePropsRef:r}=L(s);return{labelField:n,nodeProps:r,renderLabel:e,renderOption:t}},render(){let{clsPrefix:e,renderLabel:t,renderOption:n,nodeProps:r,tmNode:{rawNode:i}}=this,a=r?.(i),o=t?t(i,!1):Te(i[this.labelField],i,!1),s=H(`div`,Object.assign({},a,{class:[`${e}-base-select-group-header`,a?.class]}),o);return i.render?i.render({node:s,option:i}):n?n({node:s,option:i,selected:!1}):s}});function ht(e,t){return H(F,{name:`fade-in-scale-up-transition`},{default:()=>e?H(x,{clsPrefix:t,class:`${t}-base-select-option__check`},{default:()=>H(Ee)}):null})}var gt=V({name:`NBaseSelectOption`,props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(e){let{valueRef:t,pendingTmNodeRef:n,multipleRef:r,valueSetRef:i,renderLabelRef:a,renderOptionRef:o,labelFieldRef:c,valueFieldRef:l,showCheckmarkRef:u,nodePropsRef:d,handleOptionClick:f,handleOptionMouseEnter:p}=L(s),m=le(()=>{let{value:t}=n;return t?e.tmNode.key===t.key:!1});function h(t){let{tmNode:n}=e;n.disabled||f(t,n)}function g(t){let{tmNode:n}=e;n.disabled||p(t,n)}function _(t){let{tmNode:n}=e,{value:r}=m;n.disabled||r||p(t,n)}return{multiple:r,isGrouped:le(()=>{let{tmNode:t}=e,{parent:n}=t;return n&&n.rawNode.type===`group`}),showCheckmark:u,nodeProps:d,isPending:m,isSelected:le(()=>{let{value:n}=t,{value:a}=r;if(n===null)return!1;let o=e.tmNode.rawNode[l.value];if(a){let{value:e}=i;return e.has(o)}else return n===o}),labelField:c,renderLabel:a,renderOption:o,handleMouseMove:_,handleMouseEnter:g,handleClick:h}},render(){let{clsPrefix:e,tmNode:{rawNode:t},isSelected:n,isPending:r,isGrouped:i,showCheckmark:a,nodeProps:o,renderOption:s,renderLabel:c,handleClick:l,handleMouseEnter:u,handleMouseMove:d}=this,f=ht(n,e),p=c?[c(t,n),a&&f]:[Te(t[this.labelField],t,n),a&&f],m=o?.(t),h=H(`div`,Object.assign({},m,{class:[`${e}-base-select-option`,t.class,m?.class,{[`${e}-base-select-option--disabled`]:t.disabled,[`${e}-base-select-option--selected`]:n,[`${e}-base-select-option--grouped`]:i,[`${e}-base-select-option--pending`]:r,[`${e}-base-select-option--show-checkmark`]:a}],style:[m?.style||``,t.style||``],onClick:we([l,m?.onClick]),onMouseenter:we([u,m?.onMouseenter]),onMousemove:we([d,m?.onMousemove])}),H(`div`,{class:`${e}-base-select-option__content`},p));return t.render?t.render({node:h,option:t,selected:n}):s?s({node:h,option:t,selected:n}):h}}),_t=Q(`base-select-menu`,`
 line-height: 1.5;
 outline: none;
 z-index: 0;
 position: relative;
 border-radius: var(--n-border-radius);
 transition:
 background-color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier);
 background-color: var(--n-color);
`,[Q(`scrollbar`,`
 max-height: var(--n-height);
 `),Q(`virtual-list`,`
 max-height: var(--n-height);
 `),Q(`base-select-option`,`
 min-height: var(--n-option-height);
 font-size: var(--n-option-font-size);
 display: flex;
 align-items: center;
 `,[M(`content`,`
 z-index: 1;
 white-space: nowrap;
 text-overflow: ellipsis;
 overflow: hidden;
 `)]),Q(`base-select-group-header`,`
 min-height: var(--n-option-height);
 font-size: .93em;
 display: flex;
 align-items: center;
 `),Q(`base-select-menu-option-wrapper`,`
 position: relative;
 width: 100%;
 `),M(`loading, empty`,`
 display: flex;
 padding: 12px 32px;
 flex: 1;
 justify-content: center;
 `),M(`loading`,`
 color: var(--n-loading-color);
 font-size: var(--n-loading-size);
 `),M(`header`,`
 padding: 8px var(--n-option-padding-left);
 font-size: var(--n-option-font-size);
 transition: 
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 border-bottom: 1px solid var(--n-action-divider-color);
 color: var(--n-action-text-color);
 `),M(`action`,`
 padding: 8px var(--n-option-padding-left);
 font-size: var(--n-option-font-size);
 transition: 
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 border-top: 1px solid var(--n-action-divider-color);
 color: var(--n-action-text-color);
 `),Q(`base-select-group-header`,`
 position: relative;
 cursor: default;
 padding: var(--n-option-padding);
 color: var(--n-group-header-text-color);
 `),Q(`base-select-option`,`
 cursor: pointer;
 position: relative;
 padding: var(--n-option-padding);
 transition:
 color .3s var(--n-bezier),
 opacity .3s var(--n-bezier);
 box-sizing: border-box;
 color: var(--n-option-text-color);
 opacity: 1;
 `,[X(`show-checkmark`,`
 padding-right: calc(var(--n-option-padding-right) + 20px);
 `),G(`&::before`,`
 content: "";
 position: absolute;
 left: 4px;
 right: 4px;
 top: 0;
 bottom: 0;
 border-radius: var(--n-border-radius);
 transition: background-color .3s var(--n-bezier);
 `),G(`&:active`,`
 color: var(--n-option-text-color-pressed);
 `),X(`grouped`,`
 padding-left: calc(var(--n-option-padding-left) * 1.5);
 `),X(`pending`,[G(`&::before`,`
 background-color: var(--n-option-color-pending);
 `)]),X(`selected`,`
 color: var(--n-option-text-color-active);
 `,[G(`&::before`,`
 background-color: var(--n-option-color-active);
 `),X(`pending`,[G(`&::before`,`
 background-color: var(--n-option-color-active-pending);
 `)])]),X(`disabled`,`
 cursor: not-allowed;
 `,[B(`selected`,`
 color: var(--n-option-text-color-disabled);
 `),X(`selected`,`
 opacity: var(--n-option-opacity-disabled);
 `)]),M(`check`,`
 font-size: 16px;
 position: absolute;
 right: calc(var(--n-option-padding-right) - 4px);
 top: calc(50% - 7px);
 color: var(--n-option-check-color);
 transition: color .3s var(--n-bezier);
 `,[T({enterScale:`0.5`})])])]),vt=V({name:`InternalSelectMenu`,props:Object.assign(Object.assign({},Z.props),{clsPrefix:{type:String,required:!0},scrollable:{type:Boolean,default:!0},treeMate:{type:Object,required:!0},multiple:Boolean,size:{type:String,default:`medium`},value:{type:[String,Number,Array],default:null},autoPending:Boolean,virtualScroll:{type:Boolean,default:!0},show:{type:Boolean,default:!0},labelField:{type:String,default:`label`},valueField:{type:String,default:`value`},loading:Boolean,focusable:Boolean,renderLabel:Function,renderOption:Function,nodeProps:Function,showCheckmark:{type:Boolean,default:!0},onMousedown:Function,onScroll:Function,onFocus:Function,onBlur:Function,onKeyup:Function,onKeydown:Function,onTabOut:Function,onMouseenter:Function,onMouseleave:Function,onResize:Function,resetMenuOnOptionsChange:{type:Boolean,default:!0},inlineThemeDisabled:Boolean,scrollbarProps:Object,onToggle:Function}),setup(e){let{mergedClsPrefixRef:t,mergedRtlRef:n,mergedComponentPropsRef:r}=ve(e),i=_(`InternalSelectMenu`,n,t),a=Z(`InternalSelectMenu`,`-internal-select-menu`,_t,ce,e,z(e,`clsPrefix`)),o=R(null),c=R(null),l=R(null),u=P(()=>e.treeMate.getFlattenedNodes()),d=P(()=>qe(u.value)),f=R(null);function p(){let{treeMate:t}=e,n=null,{value:r}=e;r===null?n=t.getFirstAvailableNode():(n=e.multiple?t.getNode((r||[])[(r||[]).length-1]):t.getNode(r),(!n||n.disabled)&&(n=t.getFirstAvailableNode())),I(n||null)}function m(){let{value:t}=f;t&&!e.treeMate.getNode(t.key)&&(f.value=null)}let h;J(()=>e.show,t=>{t?h=J(()=>e.treeMate,()=>{e.resetMenuOnOptionsChange?(e.autoPending?p():m(),ge(L)):m()},{immediate:!0}):h?.()},{immediate:!0}),K(()=>{h?.()});let g=P(()=>y(a.value.self[N(`optionHeight`,e.size)])),v=P(()=>A(a.value.self[N(`padding`,e.size)])),b=P(()=>e.multiple&&Array.isArray(e.value)?new Set(e.value):new Set),x=P(()=>{let e=u.value;return e&&e.length===0}),S=P(()=>r?.value?.Select?.renderEmpty);function C(t){let{onToggle:n}=e;n&&n(t)}function w(t){let{onScroll:n}=e;n&&n(t)}function ee(e){var t;(t=l.value)==null||t.sync(),w(e)}function T(){var e;(e=l.value)==null||e.sync()}function E(){let{value:e}=f;return e||null}function k(e,t){t.disabled||I(t,!1)}function te(e,t){t.disabled||C(t)}function ne(t){var n;O(t,`action`)||(n=e.onKeyup)==null||n.call(e,t)}function re(t){var n;O(t,`action`)||(n=e.onKeydown)==null||n.call(e,t)}function ie(t){var n;(n=e.onMousedown)==null||n.call(e,t),!e.focusable&&t.preventDefault()}function M(){let{value:e}=f;e&&I(e.getNext({loop:!0}),!0)}function F(){let{value:e}=f;e&&I(e.getPrev({loop:!0}),!0)}function I(e,t=!1){f.value=e,t&&L()}function L(){var t,n;let r=f.value;if(!r)return;let i=d.value(r.key);i!==null&&(e.virtualScroll?(t=c.value)==null||t.scrollTo({index:i}):(n=l.value)==null||n.scrollTo({index:i,elSize:g.value}))}function ae(t){var n;o.value?.contains(t.target)&&((n=e.onFocus)==null||n.call(e,t))}function B(t){var n;o.value?.contains(t.relatedTarget)||(n=e.onBlur)==null||n.call(e,t)}_e(s,{handleOptionMouseEnter:k,handleOptionClick:te,valueSetRef:b,pendingTmNodeRef:f,nodePropsRef:z(e,`nodeProps`),showCheckmarkRef:z(e,`showCheckmark`),multipleRef:z(e,`multiple`),valueRef:z(e,`value`),renderLabelRef:z(e,`renderLabel`),renderOptionRef:z(e,`renderOption`),labelFieldRef:z(e,`labelField`),valueFieldRef:z(e,`valueField`)}),_e(D,o),Y(()=>{let{value:e}=l;e&&e.sync()});let V=P(()=>{let{size:t}=e,{common:{cubicBezierEaseInOut:n},self:{height:r,borderRadius:i,color:o,groupHeaderTextColor:s,actionDividerColor:c,optionTextColorPressed:l,optionTextColor:u,optionTextColorDisabled:d,optionTextColorActive:f,optionOpacityDisabled:p,optionCheckColor:m,actionTextColor:h,optionColorPending:g,optionColorActive:_,loadingColor:v,loadingSize:y,optionColorActivePending:b,[N(`optionFontSize`,t)]:x,[N(`optionHeight`,t)]:S,[N(`optionPadding`,t)]:C}}=a.value;return{"--n-height":r,"--n-action-divider-color":c,"--n-action-text-color":h,"--n-bezier":n,"--n-border-radius":i,"--n-color":o,"--n-option-font-size":x,"--n-group-header-text-color":s,"--n-option-check-color":m,"--n-option-color-pending":g,"--n-option-color-active":_,"--n-option-color-active-pending":b,"--n-option-height":S,"--n-option-opacity-disabled":p,"--n-option-text-color":u,"--n-option-text-color-active":f,"--n-option-text-color-disabled":d,"--n-option-text-color-pressed":l,"--n-option-padding":C,"--n-option-padding-left":A(C,`left`),"--n-option-padding-right":A(C,`right`),"--n-loading-color":v,"--n-loading-size":y}}),{inlineThemeDisabled:H}=e,oe=H?j(`internal-select-menu`,P(()=>e.size[0]),V,e):void 0,U={selfRef:o,next:M,prev:F,getPendingTmNode:E};return Se(o,e.onResize),Object.assign({mergedTheme:a,mergedClsPrefix:t,rtlEnabled:i,virtualListRef:c,scrollbarRef:l,itemSize:g,padding:v,flattenedNodes:u,empty:x,mergedRenderEmpty:S,virtualListContainer(){let{value:e}=c;return e?.listElRef},virtualListContent(){let{value:e}=c;return e?.itemsElRef},doScroll:w,handleFocusin:ae,handleFocusout:B,handleKeyUp:ne,handleKeyDown:re,handleMouseDown:ie,handleVirtualListResize:T,handleVirtualListScroll:ee,cssVars:H?void 0:V,themeClass:oe?.themeClass,onRender:oe?.onRender},U)},render(){let{$slots:e,virtualScroll:t,clsPrefix:n,mergedTheme:i,themeClass:a,onRender:o}=this;return o?.(),H(`div`,{ref:`selfRef`,tabindex:this.focusable?0:-1,class:[`${n}-base-select-menu`,`${n}-base-select-menu--${this.size}-size`,this.rtlEnabled&&`${n}-base-select-menu--rtl`,a,this.multiple&&`${n}-base-select-menu--multiple`],style:this.cssVars,onFocusin:this.handleFocusin,onFocusout:this.handleFocusout,onKeyup:this.handleKeyUp,onKeydown:this.handleKeyDown,onMousedown:this.handleMouseDown,onMouseenter:this.onMouseenter,onMouseleave:this.onMouseleave},C(e.header,e=>e&&H(`div`,{class:`${n}-base-select-menu__header`,"data-header":!0,key:`header`},e)),this.loading?H(`div`,{class:`${n}-base-select-menu__loading`},H(w,{clsPrefix:n,strokeWidth:20})):this.empty?H(`div`,{class:`${n}-base-select-menu__empty`,"data-empty":!0},r(e.empty,()=>[this.mergedRenderEmpty?.call(this)||H(pt,{theme:i.peers.Empty,themeOverrides:i.peerOverrides.Empty,size:this.size})])):H(k,Object.assign({ref:`scrollbarRef`,theme:i.peers.Scrollbar,themeOverrides:i.peerOverrides.Scrollbar,scrollable:this.scrollable,container:t?this.virtualListContainer:void 0,content:t?this.virtualListContent:void 0,onScroll:t?void 0:this.doScroll},this.scrollbarProps),{default:()=>t?H(u,{ref:`virtualListRef`,class:`${n}-virtual-list`,items:this.flattenedNodes,itemSize:this.itemSize,showScrollbar:!1,paddingTop:this.padding.top,paddingBottom:this.padding.bottom,onResize:this.handleVirtualListResize,onScroll:this.handleVirtualListScroll,itemResizable:!0},{default:({item:e})=>e.isGroup?H(mt,{key:e.key,clsPrefix:n,tmNode:e}):e.ignored?null:H(gt,{clsPrefix:n,key:e.key,tmNode:e})}):H(`div`,{class:`${n}-base-select-menu-option-wrapper`,style:{paddingTop:this.padding.top,paddingBottom:this.padding.bottom}},this.flattenedNodes.map(e=>e.isGroup?H(mt,{key:e.key,clsPrefix:n,tmNode:e}):H(gt,{clsPrefix:n,key:e.key,tmNode:e})))}),C(e.action,e=>e&&[H(`div`,{class:`${n}-base-select-menu__action`,"data-action":!0,key:`action`},e),H(te,{onFocus:this.onTabOut,key:`focus-detector`})]))}});function yt(e){let{textColor2:t,primaryColorHover:n,primaryColorPressed:r,primaryColor:i,infoColor:a,successColor:o,warningColor:s,errorColor:c,baseColor:l,borderColor:u,opacityDisabled:d,tagColor:f,closeIconColor:p,closeIconColorHover:m,closeIconColorPressed:h,borderRadiusSmall:g,fontSizeMini:_,fontSizeTiny:v,fontSizeSmall:y,fontSizeMedium:b,heightMini:x,heightTiny:S,heightSmall:C,heightMedium:w,closeColorHover:ee,closeColorPressed:T,buttonColor2Hover:E,buttonColor2Pressed:D,fontWeightStrong:O}=e;return Object.assign(Object.assign({},q),{closeBorderRadius:g,heightTiny:x,heightSmall:S,heightMedium:C,heightLarge:w,borderRadius:g,opacityDisabled:d,fontSizeTiny:_,fontSizeSmall:v,fontSizeMedium:y,fontSizeLarge:b,fontWeightStrong:O,textColorCheckable:t,textColorHoverCheckable:t,textColorPressedCheckable:t,textColorChecked:l,colorCheckable:`#0000`,colorHoverCheckable:E,colorPressedCheckable:D,colorChecked:i,colorCheckedHover:n,colorCheckedPressed:r,border:`1px solid ${u}`,textColor:t,color:f,colorBordered:`rgb(250, 250, 252)`,closeIconColor:p,closeIconColorHover:m,closeIconColorPressed:h,closeColorHover:ee,closeColorPressed:T,borderPrimary:`1px solid ${W(i,{alpha:.3})}`,textColorPrimary:i,colorPrimary:W(i,{alpha:.12}),colorBorderedPrimary:W(i,{alpha:.1}),closeIconColorPrimary:i,closeIconColorHoverPrimary:i,closeIconColorPressedPrimary:i,closeColorHoverPrimary:W(i,{alpha:.12}),closeColorPressedPrimary:W(i,{alpha:.18}),borderInfo:`1px solid ${W(a,{alpha:.3})}`,textColorInfo:a,colorInfo:W(a,{alpha:.12}),colorBorderedInfo:W(a,{alpha:.1}),closeIconColorInfo:a,closeIconColorHoverInfo:a,closeIconColorPressedInfo:a,closeColorHoverInfo:W(a,{alpha:.12}),closeColorPressedInfo:W(a,{alpha:.18}),borderSuccess:`1px solid ${W(o,{alpha:.3})}`,textColorSuccess:o,colorSuccess:W(o,{alpha:.12}),colorBorderedSuccess:W(o,{alpha:.1}),closeIconColorSuccess:o,closeIconColorHoverSuccess:o,closeIconColorPressedSuccess:o,closeColorHoverSuccess:W(o,{alpha:.12}),closeColorPressedSuccess:W(o,{alpha:.18}),borderWarning:`1px solid ${W(s,{alpha:.35})}`,textColorWarning:s,colorWarning:W(s,{alpha:.15}),colorBorderedWarning:W(s,{alpha:.12}),closeIconColorWarning:s,closeIconColorHoverWarning:s,closeIconColorPressedWarning:s,closeColorHoverWarning:W(s,{alpha:.12}),closeColorPressedWarning:W(s,{alpha:.18}),borderError:`1px solid ${W(c,{alpha:.23})}`,textColorError:c,colorError:W(c,{alpha:.1}),colorBorderedError:W(c,{alpha:.08}),closeIconColorError:c,closeIconColorHoverError:c,closeIconColorPressedError:c,closeColorHoverError:W(c,{alpha:.12}),closeColorPressedError:W(c,{alpha:.18})})}var bt={name:`Tag`,common:ye,self:yt},xt={color:Object,type:{type:String,default:`default`},round:Boolean,size:String,closable:Boolean,disabled:{type:Boolean,default:void 0}},St=Q(`tag`,`
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
`,[X(`strong`,`
 font-weight: var(--n-font-weight-strong);
 `),M(`border`,`
 pointer-events: none;
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 border-radius: inherit;
 border: var(--n-border);
 transition: border-color .3s var(--n-bezier);
 `),M(`icon`,`
 display: flex;
 margin: 0 4px 0 0;
 color: var(--n-text-color);
 transition: color .3s var(--n-bezier);
 font-size: var(--n-avatar-size-override);
 `),M(`avatar`,`
 display: flex;
 margin: 0 6px 0 0;
 `),M(`close`,`
 margin: var(--n-close-margin);
 transition:
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 `),X(`round`,`
 padding: 0 calc(var(--n-height) / 3);
 border-radius: calc(var(--n-height) / 2);
 `,[M(`icon`,`
 margin: 0 4px 0 calc((var(--n-height) - 8px) / -2);
 `),M(`avatar`,`
 margin: 0 6px 0 calc((var(--n-height) - 8px) / -2);
 `),X(`closable`,`
 padding: 0 calc(var(--n-height) / 4) 0 calc(var(--n-height) / 3);
 `)]),X(`icon, avatar`,[X(`round`,`
 padding: 0 calc(var(--n-height) / 3) 0 calc(var(--n-height) / 2);
 `)]),X(`disabled`,`
 cursor: not-allowed !important;
 opacity: var(--n-opacity-disabled);
 `),X(`checkable`,`
 cursor: pointer;
 box-shadow: none;
 color: var(--n-text-color-checkable);
 background-color: var(--n-color-checkable);
 `,[B(`disabled`,[G(`&:hover`,`background-color: var(--n-color-hover-checkable);`,[B(`checked`,`color: var(--n-text-color-hover-checkable);`)]),G(`&:active`,`background-color: var(--n-color-pressed-checkable);`,[B(`checked`,`color: var(--n-text-color-pressed-checkable);`)])]),X(`checked`,`
 color: var(--n-text-color-checked);
 background-color: var(--n-color-checked);
 `,[B(`disabled`,[G(`&:hover`,`background-color: var(--n-color-checked-hover);`),G(`&:active`,`background-color: var(--n-color-checked-pressed);`)])])])]),Ct=Object.assign(Object.assign(Object.assign({},Z.props),xt),{bordered:{type:Boolean,default:void 0},checked:Boolean,checkable:Boolean,strong:Boolean,triggerClickOnClose:Boolean,onClose:[Array,Function],onMouseenter:Function,onMouseleave:Function,"onUpdate:checked":Function,onUpdateChecked:Function,internalCloseFocusable:{type:Boolean,default:!0},internalCloseIsButtonTag:{type:Boolean,default:!0},onCheckedChange:Function}),wt=de(`n-tag`),Tt=V({name:`Tag`,props:Ct,slots:Object,setup(t){let n=R(null),{mergedBorderedRef:r,mergedClsPrefixRef:i,inlineThemeDisabled:a,mergedRtlRef:o,mergedComponentPropsRef:s}=ve(t),c=P(()=>t.size||s?.value?.Tag?.size||`medium`),u=Z(`Tag`,`-tag`,St,bt,t,i);_e(wt,{roundRef:z(t,`round`)});function d(){if(!t.disabled&&t.checkable){let{checked:e,onCheckedChange:n,onUpdateChecked:r,"onUpdate:checked":i}=t;r&&r(!e),i&&i(!e),n&&n(!e)}}function f(n){if(t.triggerClickOnClose||n.stopPropagation(),!t.disabled){let{onClose:r}=t;r&&e(r,n)}}let p={setTextContent(e){let{value:t}=n;t&&(t.textContent=e)}},m=_(`Tag`,o,i),h=P(()=>{let{type:e,color:{color:n,textColor:i}={}}=t,a=c.value,{common:{cubicBezierEaseInOut:o},self:{padding:s,closeMargin:l,borderRadius:d,opacityDisabled:f,textColorCheckable:p,textColorHoverCheckable:m,textColorPressedCheckable:h,textColorChecked:g,colorCheckable:_,colorHoverCheckable:v,colorPressedCheckable:y,colorChecked:b,colorCheckedHover:x,colorCheckedPressed:S,closeBorderRadius:C,fontWeightStrong:w,[N(`colorBordered`,e)]:ee,[N(`closeSize`,a)]:T,[N(`closeIconSize`,a)]:E,[N(`fontSize`,a)]:D,[N(`height`,a)]:O,[N(`color`,e)]:k,[N(`textColor`,e)]:te,[N(`border`,e)]:ne,[N(`closeIconColor`,e)]:j,[N(`closeIconColorHover`,e)]:re,[N(`closeIconColorPressed`,e)]:ie,[N(`closeColorHover`,e)]:M,[N(`closeColorPressed`,e)]:P}}=u.value,F=A(l);return{"--n-font-weight-strong":w,"--n-avatar-size-override":`calc(${O} - 8px)`,"--n-bezier":o,"--n-border-radius":d,"--n-border":ne,"--n-close-icon-size":E,"--n-close-color-pressed":P,"--n-close-color-hover":M,"--n-close-border-radius":C,"--n-close-icon-color":j,"--n-close-icon-color-hover":re,"--n-close-icon-color-pressed":ie,"--n-close-icon-color-disabled":j,"--n-close-margin-top":F.top,"--n-close-margin-right":F.right,"--n-close-margin-bottom":F.bottom,"--n-close-margin-left":F.left,"--n-close-size":T,"--n-color":n||(r.value?ee:k),"--n-color-checkable":_,"--n-color-checked":b,"--n-color-checked-hover":x,"--n-color-checked-pressed":S,"--n-color-hover-checkable":v,"--n-color-pressed-checkable":y,"--n-font-size":D,"--n-height":O,"--n-opacity-disabled":f,"--n-padding":s,"--n-text-color":i||te,"--n-text-color-checkable":p,"--n-text-color-checked":g,"--n-text-color-hover-checkable":m,"--n-text-color-pressed-checkable":h}}),g=a?j(`tag`,P(()=>{let e=``,{type:n,color:{color:i,textColor:a}={}}=t;return e+=n[0],e+=c.value[0],i&&(e+=`a${l(i)}`),a&&(e+=`b${l(a)}`),r.value&&(e+=`c`),e}),h,t):void 0;return Object.assign(Object.assign({},p),{rtlEnabled:m,mergedClsPrefix:i,contentRef:n,mergedBordered:r,handleClick:d,handleCloseClick:f,cssVars:a?void 0:h,themeClass:g?.themeClass,onRender:g?.onRender})},render(){var e;let{mergedClsPrefix:t,rtlEnabled:n,closable:r,color:{borderColor:i}={},round:a,onRender:o,$slots:s}=this;o?.();let c=C(s.avatar,e=>e&&H(`div`,{class:`${t}-tag__avatar`},e)),l=C(s.icon,e=>e&&H(`div`,{class:`${t}-tag__icon`},e));return H(`div`,{class:[`${t}-tag`,this.themeClass,{[`${t}-tag--rtl`]:n,[`${t}-tag--strong`]:this.strong,[`${t}-tag--disabled`]:this.disabled,[`${t}-tag--checkable`]:this.checkable,[`${t}-tag--checked`]:this.checkable&&this.checked,[`${t}-tag--round`]:a,[`${t}-tag--avatar`]:c,[`${t}-tag--icon`]:l,[`${t}-tag--closable`]:r}],style:this.cssVars,onClick:this.handleClick,onMouseenter:this.onMouseenter,onMouseleave:this.onMouseleave},l||c,H(`span`,{class:`${t}-tag__content`,ref:`contentRef`},(e=this.$slots).default?.call(e)),!this.checkable&&r?H(Ae,{clsPrefix:t,class:`${t}-tag__close`,disabled:this.disabled,onClick:this.handleCloseClick,focusable:this.internalCloseFocusable,round:a,isButtonTag:this.internalCloseIsButtonTag,absolute:!0}):null,!this.checkable&&this.mergedBordered?H(`div`,{class:`${t}-tag__border`,style:{borderColor:i}}):null)}}),Et=G([Q(`base-selection`,`
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
 `,[Q(`base-loading`,`
 color: var(--n-loading-color);
 `),Q(`base-selection-tags`,`min-height: var(--n-height);`),M(`border, state-border`,`
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
 `),M(`state-border`,`
 z-index: 1;
 border-color: #0000;
 `),Q(`base-suffix`,`
 cursor: pointer;
 position: absolute;
 top: 50%;
 transform: translateY(-50%);
 right: 10px;
 `,[M(`arrow`,`
 font-size: var(--n-arrow-size);
 color: var(--n-arrow-color);
 transition: color .3s var(--n-bezier);
 `)]),Q(`base-selection-overlay`,`
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
 `,[M(`wrapper`,`
 flex-basis: 0;
 flex-grow: 1;
 overflow: hidden;
 text-overflow: ellipsis;
 `)]),Q(`base-selection-placeholder`,`
 color: var(--n-placeholder-color);
 `,[M(`inner`,`
 max-width: 100%;
 overflow: hidden;
 `)]),Q(`base-selection-tags`,`
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
 `),Q(`base-selection-label`,`
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
 `,[Q(`base-selection-input`,`
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
 `,[M(`content`,`
 text-overflow: ellipsis;
 overflow: hidden;
 white-space: nowrap; 
 `)]),M(`render-label`,`
 color: var(--n-text-color);
 `)]),B(`disabled`,[G(`&:hover`,[M(`state-border`,`
 box-shadow: var(--n-box-shadow-hover);
 border: var(--n-border-hover);
 `)]),X(`focus`,[M(`state-border`,`
 box-shadow: var(--n-box-shadow-focus);
 border: var(--n-border-focus);
 `)]),X(`active`,[M(`state-border`,`
 box-shadow: var(--n-box-shadow-active);
 border: var(--n-border-active);
 `),Q(`base-selection-label`,`background-color: var(--n-color-active);`),Q(`base-selection-tags`,`background-color: var(--n-color-active);`)])]),X(`disabled`,`cursor: not-allowed;`,[M(`arrow`,`
 color: var(--n-arrow-color-disabled);
 `),Q(`base-selection-label`,`
 cursor: not-allowed;
 background-color: var(--n-color-disabled);
 `,[Q(`base-selection-input`,`
 cursor: not-allowed;
 color: var(--n-text-color-disabled);
 `),M(`render-label`,`
 color: var(--n-text-color-disabled);
 `)]),Q(`base-selection-tags`,`
 cursor: not-allowed;
 background-color: var(--n-color-disabled);
 `),Q(`base-selection-placeholder`,`
 cursor: not-allowed;
 color: var(--n-placeholder-color-disabled);
 `)]),Q(`base-selection-input-tag`,`
 height: calc(var(--n-height) - 6px);
 line-height: calc(var(--n-height) - 6px);
 outline: none;
 display: none;
 position: relative;
 margin-bottom: 3px;
 max-width: 100%;
 vertical-align: bottom;
 `,[M(`input`,`
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
 `),M(`mirror`,`
 position: absolute;
 left: 0;
 top: 0;
 white-space: pre;
 visibility: hidden;
 user-select: none;
 -webkit-user-select: none;
 opacity: 0;
 `)]),[`warning`,`error`].map(e=>X(`${e}-status`,[M(`state-border`,`border: var(--n-border-${e});`),B(`disabled`,[G(`&:hover`,[M(`state-border`,`
 box-shadow: var(--n-box-shadow-hover-${e});
 border: var(--n-border-hover-${e});
 `)]),X(`active`,[M(`state-border`,`
 box-shadow: var(--n-box-shadow-active-${e});
 border: var(--n-border-active-${e});
 `),Q(`base-selection-label`,`background-color: var(--n-color-active-${e});`),Q(`base-selection-tags`,`background-color: var(--n-color-active-${e});`)]),X(`focus`,[M(`state-border`,`
 box-shadow: var(--n-box-shadow-focus-${e});
 border: var(--n-border-focus-${e});
 `)])])]))]),Q(`base-selection-popover`,`
 margin-bottom: -3px;
 display: flex;
 flex-wrap: wrap;
 margin-right: -8px;
 `),Q(`base-selection-tag-wrapper`,`
 max-width: 100%;
 display: inline-flex;
 padding: 0 7px 3px 0;
 `,[G(`&:last-child`,`padding-right: 0;`),Q(`tag`,`
 font-size: 14px;
 max-width: 100%;
 `,[M(`content`,`
 line-height: 1.25;
 text-overflow: ellipsis;
 overflow: hidden;
 `)])])]),Dt=V({name:`InternalSelection`,props:Object.assign(Object.assign({},Z.props),{clsPrefix:{type:String,required:!0},bordered:{type:Boolean,default:void 0},active:Boolean,pattern:{type:String,default:``},placeholder:String,selectedOption:{type:Object,default:null},selectedOptions:{type:Array,default:null},labelField:{type:String,default:`label`},valueField:{type:String,default:`value`},multiple:Boolean,filterable:Boolean,clearable:Boolean,disabled:Boolean,size:{type:String,default:`medium`},loading:Boolean,autofocus:Boolean,showArrow:{type:Boolean,default:!0},inputProps:Object,focused:Boolean,renderTag:Function,onKeydown:Function,onClick:Function,onBlur:Function,onFocus:Function,onDeleteOption:Function,maxTagCount:[String,Number],ellipsisTagPopoverProps:Object,onClear:Function,onPatternInput:Function,onPatternFocus:Function,onPatternBlur:Function,renderLabel:Function,status:String,inlineThemeDisabled:Boolean,ignoreComposition:{type:Boolean,default:!0},onResize:Function}),setup(e){let{mergedClsPrefixRef:t,mergedRtlRef:n}=ve(e),r=_(`InternalSelection`,n,t),i=R(null),a=R(null),o=R(null),s=R(null),c=R(null),l=R(null),u=R(null),d=R(null),f=R(null),p=R(null),m=R(!1),h=R(!1),g=R(!1),v=Z(`InternalSelection`,`-internal-selection`,Et,me,e,z(e,`clsPrefix`)),y=P(()=>e.clearable&&!e.disabled&&(g.value||e.active)),b=P(()=>e.selectedOption?e.renderTag?e.renderTag({option:e.selectedOption,handleClose:()=>{}}):e.renderLabel?e.renderLabel(e.selectedOption,!0):Te(e.selectedOption[e.labelField],e.selectedOption,!0):e.placeholder),x=P(()=>{let t=e.selectedOption;if(t)return t[e.labelField]}),S=P(()=>e.multiple?!!(Array.isArray(e.selectedOptions)&&e.selectedOptions.length):e.selectedOption!==null);function C(){var t;let{value:n}=i;if(n){let{value:r}=a;r&&(r.style.width=`${n.offsetWidth}px`,e.maxTagCount!==`responsive`&&((t=f.value)==null||t.sync({showAllItemsBeforeCalculate:!1})))}}function w(){let{value:e}=p;e&&(e.style.display=`none`)}function ee(){let{value:e}=p;e&&(e.style.display=`inline-block`)}J(z(e,`active`),e=>{e||w()}),J(z(e,`pattern`),()=>{e.multiple&&ge(C)});function T(t){let{onFocus:n}=e;n&&n(t)}function E(t){let{onBlur:n}=e;n&&n(t)}function D(t){let{onDeleteOption:n}=e;n&&n(t)}function O(t){let{onClear:n}=e;n&&n(t)}function k(t){let{onPatternInput:n}=e;n&&n(t)}function te(e){(!e.relatedTarget||!o.value?.contains(e.relatedTarget))&&T(e)}function ne(e){o.value?.contains(e.relatedTarget)||E(e)}function re(e){O(e)}function ie(){g.value=!0}function M(){g.value=!1}function F(t){!e.active||!e.filterable||t.target!==a.value&&t.preventDefault()}function I(e){D(e)}let L=R(!1);function ae(t){if(t.key===`Backspace`&&!L.value&&!e.pattern.length){let{selectedOptions:t}=e;t?.length&&I(t[t.length-1])}}let B=null;function V(t){let{value:n}=i;n&&(n.textContent=t.target.value,C()),e.ignoreComposition&&L.value?B=t:k(t)}function H(){L.value=!0}function oe(){L.value=!1,e.ignoreComposition&&k(B),B=null}function U(t){var n;h.value=!0,(n=e.onPatternFocus)==null||n.call(e,t)}function W(t){var n;h.value=!1,(n=e.onPatternBlur)==null||n.call(e,t)}function G(){var t,n;if(e.filterable)h.value=!1,(t=l.value)==null||t.blur(),(n=a.value)==null||n.blur();else if(e.multiple){let{value:e}=s;e?.blur()}else{let{value:e}=c;e?.blur()}}function se(){var t,n,r;e.filterable?(h.value=!1,(t=l.value)==null||t.focus()):e.multiple?(n=s.value)==null||n.focus():(r=c.value)==null||r.focus()}function ce(){let{value:e}=a;e&&(ee(),e.focus())}function le(){let{value:e}=a;e&&e.blur()}function de(e){let{value:t}=u;t&&t.setTextContent(`+${e}`)}function K(){let{value:e}=d;return e}function fe(){return a.value}let q=null;function pe(){q!==null&&window.clearTimeout(q)}function he(){e.active||(pe(),q=window.setTimeout(()=>{S.value&&(m.value=!0)},100))}function _e(){pe()}function X(e){e||(pe(),m.value=!1)}J(S,e=>{e||(m.value=!1)}),Y(()=>{ue(()=>{let t=l.value;t&&(e.disabled?t.removeAttribute(`tabindex`):t.tabIndex=h.value?-1:0)})}),Se(o,e.onResize);let{inlineThemeDisabled:Q}=e,ye=P(()=>{let{size:t}=e,{common:{cubicBezierEaseInOut:n},self:{fontWeight:r,borderRadius:i,color:a,placeholderColor:o,textColor:s,paddingSingle:c,paddingMultiple:l,caretColor:u,colorDisabled:d,textColorDisabled:f,placeholderColorDisabled:p,colorActive:m,boxShadowFocus:h,boxShadowActive:g,boxShadowHover:_,border:y,borderFocus:b,borderHover:x,borderActive:S,arrowColor:C,arrowColorDisabled:w,loadingColor:ee,colorActiveWarning:T,boxShadowFocusWarning:E,boxShadowActiveWarning:D,boxShadowHoverWarning:O,borderWarning:k,borderFocusWarning:te,borderHoverWarning:ne,borderActiveWarning:j,colorActiveError:re,boxShadowFocusError:ie,boxShadowActiveError:M,boxShadowHoverError:P,borderError:F,borderFocusError:I,borderHoverError:L,borderActiveError:ae,clearColor:R,clearColorHover:z,clearColorPressed:B,clearSize:V,arrowSize:H,[N(`height`,t)]:oe,[N(`fontSize`,t)]:U}}=v.value,W=A(c),G=A(l);return{"--n-bezier":n,"--n-border":y,"--n-border-active":S,"--n-border-focus":b,"--n-border-hover":x,"--n-border-radius":i,"--n-box-shadow-active":g,"--n-box-shadow-focus":h,"--n-box-shadow-hover":_,"--n-caret-color":u,"--n-color":a,"--n-color-active":m,"--n-color-disabled":d,"--n-font-size":U,"--n-height":oe,"--n-padding-single-top":W.top,"--n-padding-multiple-top":G.top,"--n-padding-single-right":W.right,"--n-padding-multiple-right":G.right,"--n-padding-single-left":W.left,"--n-padding-multiple-left":G.left,"--n-padding-single-bottom":W.bottom,"--n-padding-multiple-bottom":G.bottom,"--n-placeholder-color":o,"--n-placeholder-color-disabled":p,"--n-text-color":s,"--n-text-color-disabled":f,"--n-arrow-color":C,"--n-arrow-color-disabled":w,"--n-loading-color":ee,"--n-color-active-warning":T,"--n-box-shadow-focus-warning":E,"--n-box-shadow-active-warning":D,"--n-box-shadow-hover-warning":O,"--n-border-warning":k,"--n-border-focus-warning":te,"--n-border-hover-warning":ne,"--n-border-active-warning":j,"--n-color-active-error":re,"--n-box-shadow-focus-error":ie,"--n-box-shadow-active-error":M,"--n-box-shadow-hover-error":P,"--n-border-error":F,"--n-border-focus-error":I,"--n-border-hover-error":L,"--n-border-active-error":ae,"--n-clear-size":V,"--n-clear-color":R,"--n-clear-color-hover":z,"--n-clear-color-pressed":B,"--n-arrow-size":H,"--n-font-weight":r}}),$=Q?j(`internal-selection`,P(()=>e.size[0]),ye,e):void 0;return{mergedTheme:v,mergedClearable:y,mergedClsPrefix:t,rtlEnabled:r,patternInputFocused:h,filterablePlaceholder:b,label:x,selected:S,showTagsPanel:m,isComposing:L,counterRef:u,counterWrapperRef:d,patternInputMirrorRef:i,patternInputRef:a,selfRef:o,multipleElRef:s,singleElRef:c,patternInputWrapperRef:l,overflowRef:f,inputTagElRef:p,handleMouseDown:F,handleFocusin:te,handleClear:re,handleMouseEnter:ie,handleMouseLeave:M,handleDeleteOption:I,handlePatternKeyDown:ae,handlePatternInputInput:V,handlePatternInputBlur:W,handlePatternInputFocus:U,handleMouseEnterCounter:he,handleMouseLeaveCounter:_e,handleFocusout:ne,handleCompositionEnd:oe,handleCompositionStart:H,onPopoverUpdateShow:X,focus:se,focusInput:ce,blur:G,blurInput:le,updateCounter:de,getCounter:K,getTail:fe,renderLabel:e.renderLabel,cssVars:Q?void 0:ye,themeClass:$?.themeClass,onRender:$?.onRender}},render(){let{status:e,multiple:t,size:n,disabled:r,filterable:i,maxTagCount:a,bordered:o,clsPrefix:s,ellipsisTagPopoverProps:c,onRender:l,renderTag:u,renderLabel:d}=this;l?.();let p=a===`responsive`,m=typeof a==`number`,h=p||m,g=H(f,null,{default:()=>H(v,{clsPrefix:s,loading:this.loading,showArrow:this.showArrow,showClear:this.mergedClearable&&this.selected,onClear:this.handleClear},{default:()=>{var e;return(e=this.$slots).arrow?.call(e)}})}),_;if(t){let{labelField:e}=this,t=t=>H(`div`,{class:`${s}-base-selection-tag-wrapper`,key:t.value},u?u({option:t,handleClose:()=>{this.handleDeleteOption(t)}}):H(Tt,{size:n,closable:!t.disabled,disabled:r,onClose:()=>{this.handleDeleteOption(t)},internalCloseIsButtonTag:!1,internalCloseFocusable:!1},{default:()=>d?d(t,!0):Te(t[e],t,!0)})),o=()=>(m?this.selectedOptions.slice(0,a):this.selectedOptions).map(t),l=i?H(`div`,{class:`${s}-base-selection-input-tag`,ref:`inputTagElRef`,key:`__input-tag__`},H(`input`,Object.assign({},this.inputProps,{ref:`patternInputRef`,tabindex:-1,disabled:r,value:this.pattern,autofocus:this.autofocus,class:`${s}-base-selection-input-tag__input`,onBlur:this.handlePatternInputBlur,onFocus:this.handlePatternInputFocus,onKeydown:this.handlePatternKeyDown,onInput:this.handlePatternInputInput,onCompositionstart:this.handleCompositionStart,onCompositionend:this.handleCompositionEnd})),H(`span`,{ref:`patternInputMirrorRef`,class:`${s}-base-selection-input-tag__mirror`},this.pattern)):null,f=p?()=>H(`div`,{class:`${s}-base-selection-tag-wrapper`,ref:`counterWrapperRef`},H(Tt,{size:n,ref:`counterRef`,onMouseenter:this.handleMouseEnterCounter,onMouseleave:this.handleMouseLeaveCounter,disabled:r})):void 0,v;if(m){let e=this.selectedOptions.length-a;e>0&&(v=H(`div`,{class:`${s}-base-selection-tag-wrapper`,key:`__counter__`},H(Tt,{size:n,ref:`counterRef`,onMouseenter:this.handleMouseEnterCounter,disabled:r},{default:()=>`+${e}`})))}let y=p?i?H(xe,{ref:`overflowRef`,updateCounter:this.updateCounter,getCounter:this.getCounter,getTail:this.getTail,style:{width:`100%`,display:`flex`,overflow:`hidden`}},{default:o,counter:f,tail:()=>l}):H(xe,{ref:`overflowRef`,updateCounter:this.updateCounter,getCounter:this.getCounter,style:{width:`100%`,display:`flex`,overflow:`hidden`}},{default:o,counter:f}):m&&v?o().concat(v):o(),b=h?()=>H(`div`,{class:`${s}-base-selection-popover`},p?o():this.selectedOptions.map(t)):void 0,x=h?Object.assign({show:this.showTagsPanel,trigger:`hover`,overlap:!0,placement:`top`,width:`trigger`,onUpdateShow:this.onPopoverUpdateShow,theme:this.mergedTheme.peers.Popover,themeOverrides:this.mergedTheme.peerOverrides.Popover},c):null,S=!this.selected&&(!this.active||!this.pattern&&!this.isComposing)?H(`div`,{class:`${s}-base-selection-placeholder ${s}-base-selection-overlay`},H(`div`,{class:`${s}-base-selection-placeholder__inner`},this.placeholder)):null,C=i?H(`div`,{ref:`patternInputWrapperRef`,class:`${s}-base-selection-tags`},y,p?null:l,g):H(`div`,{ref:`multipleElRef`,class:`${s}-base-selection-tags`,tabindex:r?void 0:0},y,g);_=H(ae,null,h?H(ie,Object.assign({},x,{scrollable:!0,style:`max-height: calc(var(--v-target-height) * 6.6);`}),{trigger:()=>C,default:b}):C,S)}else if(i){let e=this.pattern||this.isComposing,t=this.active?!e:!this.selected,n=this.active?!1:this.selected;_=H(`div`,{ref:`patternInputWrapperRef`,class:`${s}-base-selection-label`,title:this.patternInputFocused?void 0:Ce(this.label)},H(`input`,Object.assign({},this.inputProps,{ref:`patternInputRef`,class:`${s}-base-selection-input`,value:this.active?this.pattern:``,placeholder:``,readonly:r,disabled:r,tabindex:-1,autofocus:this.autofocus,onFocus:this.handlePatternInputFocus,onBlur:this.handlePatternInputBlur,onInput:this.handlePatternInputInput,onCompositionstart:this.handleCompositionStart,onCompositionend:this.handleCompositionEnd})),n?H(`div`,{class:`${s}-base-selection-label__render-label ${s}-base-selection-overlay`,key:`input`},H(`div`,{class:`${s}-base-selection-overlay__wrapper`},u?u({option:this.selectedOption,handleClose:()=>{}}):d?d(this.selectedOption,!0):Te(this.label,this.selectedOption,!0))):null,t?H(`div`,{class:`${s}-base-selection-placeholder ${s}-base-selection-overlay`,key:`placeholder`},H(`div`,{class:`${s}-base-selection-overlay__wrapper`},this.filterablePlaceholder)):null,g)}else _=H(`div`,{ref:`singleElRef`,class:`${s}-base-selection-label`,tabindex:this.disabled?void 0:0},this.label===void 0?H(`div`,{class:`${s}-base-selection-placeholder ${s}-base-selection-overlay`,key:`placeholder`},H(`div`,{class:`${s}-base-selection-placeholder__inner`},this.placeholder)):H(`div`,{class:`${s}-base-selection-input`,title:Ce(this.label),key:`input`},H(`div`,{class:`${s}-base-selection-input__content`},u?u({option:this.selectedOption,handleClose:()=>{}}):d?d(this.selectedOption,!0):Te(this.label,this.selectedOption,!0))),g);return H(`div`,{ref:`selfRef`,class:[`${s}-base-selection`,this.rtlEnabled&&`${s}-base-selection--rtl`,this.themeClass,e&&`${s}-base-selection--${e}-status`,{[`${s}-base-selection--active`]:this.active,[`${s}-base-selection--selected`]:this.selected||this.active&&this.pattern,[`${s}-base-selection--disabled`]:this.disabled,[`${s}-base-selection--multiple`]:this.multiple,[`${s}-base-selection--focus`]:this.focused}],style:this.cssVars,onClick:this.onClick,onMouseenter:this.handleMouseEnter,onMouseleave:this.handleMouseLeave,onKeydown:this.onKeydown,onFocusin:this.handleFocusin,onFocusout:this.handleFocusout,onMousedown:this.handleMouseDown},_,o?H(`div`,{class:`${s}-base-selection__border`}):null,o?H(`div`,{class:`${s}-base-selection__state-border`}):null)}});function Ot(e){return e.type===`group`}function kt(e){return e.type===`ignored`}function At(e,t){try{return!!(1+t.toString().toLowerCase().indexOf(e.trim().toLowerCase()))}catch{return!1}}function jt(e,t){return{getIsGroup:Ot,getIgnored:kt,getKey(t){return Ot(t)?t.name||t.key||`key-required`:t[e]},getChildren(e){return e[t]}}}function Mt(e,t,n,r){if(!t)return e;function i(e){if(!Array.isArray(e))return[];let a=[];for(let o of e)if(Ot(o)){let e=i(o[r]);e.length&&a.push(Object.assign({},o,{[r]:e}))}else if(kt(o))continue;else t(n,o)&&a.push(o);return a}return i(e)}function Nt(e,t,n){let r=new Map;return e.forEach(e=>{Ot(e)?e[n].forEach(e=>{r.set(e[t],e)}):r.set(e[t],e)}),r}var Pt=G([Q(`select`,`
 z-index: auto;
 outline: none;
 width: 100%;
 position: relative;
 font-weight: var(--n-font-weight);
 `),Q(`select-menu`,`
 margin: 4px 0;
 box-shadow: var(--n-menu-box-shadow);
 `,[T({originalTransition:`background-color .3s var(--n-bezier), box-shadow .3s var(--n-bezier)`})])]),Ft=V({name:`Select`,props:Object.assign(Object.assign({},Z.props),{to:p.propTo,bordered:{type:Boolean,default:void 0},clearable:Boolean,clearCreatedOptionsOnClear:{type:Boolean,default:!0},clearFilterAfterSelect:{type:Boolean,default:!0},options:{type:Array,default:()=>[]},defaultValue:{type:[String,Number,Array],default:null},keyboard:{type:Boolean,default:!0},value:[String,Number,Array],placeholder:String,menuProps:Object,multiple:Boolean,size:String,menuSize:{type:String},filterable:Boolean,disabled:{type:Boolean,default:void 0},remote:Boolean,loading:Boolean,filter:Function,placement:{type:String,default:`bottom-start`},widthMode:{type:String,default:`trigger`},tag:Boolean,onCreate:Function,fallbackOption:{type:[Function,Boolean],default:void 0},show:{type:Boolean,default:void 0},showArrow:{type:Boolean,default:!0},maxTagCount:[Number,String],ellipsisTagPopoverProps:Object,consistentMenuWidth:{type:Boolean,default:!0},virtualScroll:{type:Boolean,default:!0},labelField:{type:String,default:`label`},valueField:{type:String,default:`value`},childrenField:{type:String,default:`children`},renderLabel:Function,renderOption:Function,renderTag:Function,"onUpdate:value":[Function,Array],inputProps:Object,nodeProps:Function,ignoreComposition:{type:Boolean,default:!0},showOnFocus:Boolean,onUpdateValue:[Function,Array],onBlur:[Function,Array],onClear:[Function,Array],onFocus:[Function,Array],onScroll:[Function,Array],onSearch:[Function,Array],onUpdateShow:[Function,Array],"onUpdate:show":[Function,Array],displayDirective:{type:String,default:`show`},resetMenuOnOptionsChange:{type:Boolean,default:!0},status:String,showCheckmark:{type:Boolean,default:!0},scrollbarProps:Object,onChange:[Function,Array],items:Array}),slots:Object,setup(t){let{mergedClsPrefixRef:r,mergedBorderedRef:i,namespaceRef:a,inlineThemeDisabled:o,mergedComponentPropsRef:s}=ve(t),c=Z(`Select`,`-select`,Pt,fe,t,r),l=R(t.defaultValue),u=h(z(t,`value`),l),d=R(!1),f=R(``),m=re(t,[`items`,`options`]),_=R([]),v=R([]),y=P(()=>v.value.concat(_.value).concat(m.value)),b=P(()=>{let{filter:e}=t;if(e)return e;let{labelField:n,valueField:r}=t;return(e,t)=>{if(!t)return!1;let i=t[n];if(typeof i==`string`)return At(e,i);let a=t[r];return typeof a==`string`?At(e,a):typeof a==`number`?At(e,String(a)):!1}}),x=P(()=>{if(t.remote)return m.value;{let{value:e}=y,{value:n}=f;return!n.length||!t.filterable?e:Mt(e,b.value,n,t.childrenField)}}),C=P(()=>{let{valueField:e,childrenField:n}=t,r=jt(e,n);return dt(x.value,r)}),w=P(()=>Nt(y.value,t.valueField,t.childrenField)),T=R(!1),E=h(z(t,`show`),T),D=R(null),k=R(null),A=R(null),{localeRef:te}=ne(`Select`),ie=P(()=>t.placeholder??te.value.placeholder),M=[],N=R(new Map),F=P(()=>{let{fallbackOption:e}=t;if(e===void 0){let{labelField:e,valueField:n}=t;return t=>({[e]:String(t),[n]:t})}return e===!1?!1:t=>Object.assign(e(t),{value:t})});function I(e){let n=t.remote,{value:r}=N,{value:i}=w,{value:a}=F,o=[];return e.forEach(e=>{if(i.has(e))o.push(i.get(e));else if(n&&r.has(e))o.push(r.get(e));else if(a){let t=a(e);t&&o.push(t)}}),o}let L=P(()=>{if(t.multiple){let{value:e}=u;return Array.isArray(e)?I(e):[]}return null}),ae=P(()=>{let{value:e}=u;return!t.multiple&&!Array.isArray(e)?e===null?null:I([e])[0]||null:null}),B=n(t,{mergedSize:e=>{let{size:n}=t;if(n)return n;let{mergedSize:r}=e||{};return r?.value?r.value:s?.value?.Select?.size||`medium`}}),{mergedSizeRef:V,mergedDisabledRef:H,mergedStatusRef:oe}=B;function U(n,r){let{onChange:i,"onUpdate:value":a,onUpdateValue:o}=t,{nTriggerFormChange:s,nTriggerFormInput:c}=B;i&&e(i,n,r),o&&e(o,n,r),a&&e(a,n,r),l.value=n,s(),c()}function W(n){let{onBlur:r}=t,{nTriggerFormBlur:i}=B;r&&e(r,n),i()}function G(){let{onClear:n}=t;n&&e(n)}function se(n){let{onFocus:r,showOnFocus:i}=t,{nTriggerFormFocus:a}=B;r&&e(r,n),a(),i&&K()}function ce(n){let{onSearch:r}=t;r&&e(r,n)}function le(n){let{onScroll:r}=t;r&&e(r,n)}function ue(){var e;let{remote:n,multiple:r}=t;if(n){let{value:n}=N;if(r){let{valueField:r}=t;(e=L.value)==null||e.forEach(e=>{n.set(e[r],e)})}else{let e=ae.value;e&&n.set(e[t.valueField],e)}}}function de(n){let{onUpdateShow:r,"onUpdate:show":i}=t;r&&e(r,n),i&&e(i,n),T.value=n}function K(){H.value||(de(!0),T.value=!0,t.filterable&&je())}function q(){de(!1)}function pe(){f.value=``,v.value=M}let Y=R(!1);function me(){t.filterable&&(Y.value=!0)}function he(){t.filterable&&(Y.value=!1,E.value||pe())}function ge(){H.value||(E.value?t.filterable?je():q():K())}function _e(e){(A.value?.selfRef)?.contains(e.relatedTarget)||(d.value=!1,W(e),q())}function X(e){se(e),d.value=!0}function Q(){d.value=!0}function ye(e){D.value?.$el.contains(e.relatedTarget)||(d.value=!1,W(e),q())}function $(){var e;(e=D.value)==null||e.focus(),q()}function be(e){E.value&&(D.value?.$el.contains(ee(e))||q())}function xe(e){if(!Array.isArray(e))return[];if(F.value)return Array.from(e);{let{remote:n}=t,{value:r}=w;if(n){let{value:t}=N;return e.filter(e=>r.has(e)||t.has(e))}else return e.filter(e=>r.has(e))}}function Se(e){Ce(e.rawNode)}function Ce(e){if(H.value)return;let{tag:n,remote:r,clearFilterAfterSelect:i,valueField:a}=t;if(n&&!r){let{value:e}=v,t=e[0]||null;if(t){let e=_.value;e.length?e.push(t):_.value=[t],v.value=M}}if(r&&N.value.set(e[a],e),t.multiple){let t=xe(u.value),o=t.findIndex(t=>t===e[a]);if(~o){if(t.splice(o,1),n&&!r){let t=we(e[a]);~t&&(_.value.splice(t,1),i&&(f.value=``))}}else t.push(e[a]),i&&(f.value=``);U(t,I(t))}else{if(n&&!r){let t=we(e[a]);~t?_.value=[_.value[t]]:_.value=M}Ae(),q(),U(e[a],e)}}function we(e){return _.value.findIndex(n=>n[t.valueField]===e)}function Te(e){E.value||K();let{value:n}=e.target;f.value=n;let{tag:r,remote:i}=t;if(ce(n),r&&!i){if(!n){v.value=M;return}let{onCreate:e}=t,r=e?e(n):{[t.labelField]:n,[t.valueField]:n},{valueField:i,labelField:a}=t;m.value.some(e=>e[i]===r[i]||e[a]===r[a])||_.value.some(e=>e[i]===r[i]||e[a]===r[a])?v.value=M:v.value=[r]}}function Ee(e){e.stopPropagation();let{multiple:n,tag:r,remote:i,clearCreatedOptionsOnClear:a}=t;!n&&t.filterable&&q(),r&&!i&&a&&(_.value=M),G(),n?U([],[]):U(null,null)}function De(e){!O(e,`action`)&&!O(e,`empty`)&&!O(e,`header`)&&e.preventDefault()}function Oe(e){le(e)}function ke(e){var n,r,i;if(!t.keyboard){e.preventDefault();return}switch(e.key){case` `:if(t.filterable)break;e.preventDefault();case`Enter`:if(!D.value?.isComposing){if(E.value){let e=A.value?.getPendingTmNode();e?Se(e):t.filterable||(q(),Ae())}else if(K(),t.tag&&Y.value){let e=v.value[0];if(e){let n=e[t.valueField],{value:r}=u;t.multiple&&Array.isArray(r)&&r.includes(n)||Ce(e)}}}e.preventDefault();break;case`ArrowUp`:if(e.preventDefault(),t.loading)return;E.value&&((n=A.value)==null||n.prev());break;case`ArrowDown`:if(e.preventDefault(),t.loading)return;E.value?(r=A.value)==null||r.next():K();break;case`Escape`:E.value&&(S(e),q()),(i=D.value)==null||i.focus();break}}function Ae(){var e;(e=D.value)==null||e.focus()}function je(){var e;(e=D.value)==null||e.focusInput()}function Me(){var e;E.value&&((e=k.value)==null||e.syncPosition())}ue(),J(z(t,`options`),ue);let Ne={focus:()=>{var e;(e=D.value)==null||e.focus()},focusInput:()=>{var e;(e=D.value)==null||e.focusInput()},blur:()=>{var e;(e=D.value)==null||e.blur()},blurInput:()=>{var e;(e=D.value)==null||e.blurInput()}},Pe=P(()=>{let{self:{menuBoxShadow:e}}=c.value;return{"--n-menu-box-shadow":e}}),Fe=o?j(`select`,void 0,Pe,t):void 0;return Object.assign(Object.assign({},Ne),{mergedStatus:oe,mergedClsPrefix:r,mergedBordered:i,namespace:a,treeMate:C,isMounted:g(),triggerRef:D,menuRef:A,pattern:f,uncontrolledShow:T,mergedShow:E,adjustedTo:p(t),uncontrolledValue:l,mergedValue:u,followerRef:k,localizedPlaceholder:ie,selectedOption:ae,selectedOptions:L,mergedSize:V,mergedDisabled:H,focused:d,activeWithoutMenuOpen:Y,inlineThemeDisabled:o,onTriggerInputFocus:me,onTriggerInputBlur:he,handleTriggerOrMenuResize:Me,handleMenuFocus:Q,handleMenuBlur:ye,handleMenuTabOut:$,handleTriggerClick:ge,handleToggle:Se,handleDeleteOption:Ce,handlePatternInput:Te,handleClear:Ee,handleTriggerBlur:_e,handleTriggerFocus:X,handleKeydown:ke,handleMenuAfterLeave:pe,handleMenuClickOutside:be,handleMenuScroll:Oe,handleMenuKeydown:ke,handleMenuMousedown:De,mergedTheme:c,cssVars:o?void 0:Pe,themeClass:Fe?.themeClass,onRender:Fe?.onRender})},render(){return H(`div`,{class:`${this.mergedClsPrefix}-select`},H(a,null,{default:()=>[H(m,null,{default:()=>H(Dt,{ref:`triggerRef`,inlineThemeDisabled:this.inlineThemeDisabled,status:this.mergedStatus,inputProps:this.inputProps,clsPrefix:this.mergedClsPrefix,showArrow:this.showArrow,maxTagCount:this.maxTagCount,ellipsisTagPopoverProps:this.ellipsisTagPopoverProps,bordered:this.mergedBordered,active:this.activeWithoutMenuOpen||this.mergedShow,pattern:this.pattern,placeholder:this.localizedPlaceholder,selectedOption:this.selectedOption,selectedOptions:this.selectedOptions,multiple:this.multiple,renderTag:this.renderTag,renderLabel:this.renderLabel,filterable:this.filterable,clearable:this.clearable,disabled:this.mergedDisabled,size:this.mergedSize,theme:this.mergedTheme.peers.InternalSelection,labelField:this.labelField,valueField:this.valueField,themeOverrides:this.mergedTheme.peerOverrides.InternalSelection,loading:this.loading,focused:this.focused,onClick:this.handleTriggerClick,onDeleteOption:this.handleDeleteOption,onPatternInput:this.handlePatternInput,onClear:this.handleClear,onBlur:this.handleTriggerBlur,onFocus:this.handleTriggerFocus,onKeydown:this.handleKeydown,onPatternBlur:this.onTriggerInputBlur,onPatternFocus:this.onTriggerInputFocus,onResize:this.handleTriggerOrMenuResize,ignoreComposition:this.ignoreComposition},{arrow:()=>{var e;return[(e=this.$slots).arrow?.call(e)]}})}),H(o,{ref:`followerRef`,show:this.mergedShow,to:this.adjustedTo,teleportDisabled:this.adjustedTo===p.tdkey,containerClass:this.namespace,width:this.consistentMenuWidth?`target`:void 0,minWidth:`target`,placement:this.placement},{default:()=>H(F,{name:`fade-in-scale-up-transition`,appear:this.isMounted,onAfterLeave:this.handleMenuAfterLeave},{default:()=>{var e;return this.mergedShow||this.displayDirective===`show`?((e=this.onRender)==null||e.call(this),U(H(vt,Object.assign({},this.menuProps,{ref:`menuRef`,onResize:this.handleTriggerOrMenuResize,inlineThemeDisabled:this.inlineThemeDisabled,virtualScroll:this.consistentMenuWidth&&this.virtualScroll,class:[`${this.mergedClsPrefix}-select-menu`,this.themeClass,this.menuProps?.class],clsPrefix:this.mergedClsPrefix,focusable:!0,labelField:this.labelField,valueField:this.valueField,autoPending:!0,nodeProps:this.nodeProps,theme:this.mergedTheme.peers.InternalSelectMenu,themeOverrides:this.mergedTheme.peerOverrides.InternalSelectMenu,treeMate:this.treeMate,multiple:this.multiple,size:this.menuSize,renderOption:this.renderOption,renderLabel:this.renderLabel,value:this.mergedValue,style:[this.menuProps?.style,this.cssVars],onToggle:this.handleToggle,onScroll:this.handleMenuScroll,onFocus:this.handleMenuFocus,onBlur:this.handleMenuBlur,onKeydown:this.handleMenuKeydown,onTabOut:this.handleMenuTabOut,onMousedown:this.handleMenuMousedown,show:this.mergedShow,showCheckmark:this.showCheckmark,resetMenuOnOptionsChange:this.resetMenuOnOptionsChange,scrollbarProps:this.scrollbarProps}),{empty:()=>{var e;return[(e=this.$slots).empty?.call(e)]},header:()=>{var e;return[(e=this.$slots).header?.call(e)]},action:()=>{var e;return[(e=this.$slots).action?.call(e)]}}),this.displayDirective===`show`?[[I,this.mergedShow],[t,this.handleMenuClickOutside,void 0,{capture:!0}]]:[[t,this.handleMenuClickOutside,void 0,{capture:!0}]])):null}})})]}))}});export{Ft as t};
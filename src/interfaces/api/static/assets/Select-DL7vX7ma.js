import{A as e,B as t,C as n,D as r,E as i,G as a,L as o,M as s,N as c,O as l,R as u,S as d,T as f,W as p,_ as m,a as h,d as g,g as _,h as v,j as y,q as b,s as x,u as S,x as C,y as w,z as ee}from"./ErrorBanner-DLePGqf1.js";import{c as te,d as T,f as E,i as D,n as O,o as ne,r as k,s as A,u as re}from"./usePolling-s2S3ovsK.js";import{a as ie,n as ae}from"./GlossaryTip-C43uc96E.js";import{Ct as j,Et as M,Jt as N,Kt as P,Lt as F,Mt as oe,Pt as I,Tt as L,Vt as R,Xt as z,Zt as se,_ as B,_t as V,an as ce,bt as H,dn as U,en as le,g as ue,gn as de,gt as W,ht as G,l as fe,ln as K,m as q,mn as pe,mt as me,p as he,pn as ge,rn as _e,ut as ve,wn as J,wt as Y,x as X,xn as Z,xt as Q,y as ye}from"./index-DcgR8lOt.js";var $=`v-hidden`,be=r(`[v-hidden]`,{display:`none!important`}),xe=N({name:`Overflow`,props:{getCounter:Function,getTail:Function,updateCounter:Function,onUpdateCount:Function,onUpdateOverflow:Function},setup(e,{slots:t}){let n=Z(null),r=Z(null);function i(i){let{value:a}=n,{getCounter:o,getTail:s}=e,c;if(c=o===void 0?r.value:o(),!a||!c)return;c.hasAttribute($)&&c.removeAttribute($);let{children:l}=a;if(i.showAllItemsBeforeCalculate)for(let e of l)e.hasAttribute($)&&e.removeAttribute($);let u=a.offsetWidth,d=[],f=t.tail?s?.():null,p=f?f.offsetWidth:0,m=!1,h=a.children.length-+!!t.tail;for(let t=0;t<h-1;++t){if(t<0)continue;let n=l[t];if(m){n.hasAttribute($)||n.setAttribute($,``);continue}else n.hasAttribute($)&&n.removeAttribute($);let r=n.offsetWidth;if(p+=r,d[t]=r,p>u){let{updateCounter:n}=e;for(let r=t;r>=0;--r){let i=h-1-r;n===void 0?c.textContent=`${i}`:n(i);let a=c.offsetWidth;if(p-=d[r],p+a<=u||r===0){m=!0,t=r-1,f&&(t===-1?(f.style.maxWidth=`${u-a}px`,f.style.boxSizing=`border-box`):f.style.maxWidth=``);let{onUpdateCount:n}=e;n&&n(i);break}}}}let{onUpdateOverflow:g}=e;m?g!==void 0&&g(!0):(g!==void 0&&g(!1),c.setAttribute($,``))}let a=me();return be.mount({id:`vueuc/overflow`,head:!0,anchorMetaName:l,ssr:a}),ce(()=>i({showAllItemsBeforeCalculate:!1})),{selfRef:n,counterRef:r,sync:i}},render(){let{$slots:e}=this;return le(()=>this.sync({showAllItemsBeforeCalculate:!1})),z(`div`,{class:`v-overflow`,ref:`selfRef`},[U(e,`default`),e.counter?e.counter():z(`span`,{style:{display:`inline-block`},ref:`counterRef`}),e.tail?e.tail():null])}});function Se(e,t){t&&(ce(()=>{let{value:n}=e;n&&f.registerHandler(n,t)}),ge(e,(e,t)=>{t&&f.unregisterHandler(t)},{deep:!1}),_e(()=>{let{value:t}=e;t&&f.unregisterHandler(t)}))}function Ce(e){switch(typeof e){case`string`:return e||void 0;case`number`:return String(e);default:return}}function we(e){let t=e.filter(e=>e!==void 0);if(t.length!==0)return t.length===1?t[0]:t=>{e.forEach(e=>{e&&e(t)})}}function Te(e,...t){return typeof e==`function`?e(...t):typeof e==`string`?P(e):typeof e==`number`?P(String(e)):null}var Ee=N({name:`Checkmark`,render(){return z(`svg`,{xmlns:`http://www.w3.org/2000/svg`,viewBox:`0 0 16 16`},z(`g`,{fill:`none`},z(`path`,{d:`M14.046 3.486a.75.75 0 0 1-.032 1.06l-7.93 7.474a.85.85 0 0 1-1.188-.022l-2.68-2.72a.75.75 0 1 1 1.068-1.053l2.234 2.267l7.468-7.038a.75.75 0 0 1 1.06.032z`,fill:`currentColor`})))}}),De=ne(`close`,()=>z(`svg`,{viewBox:`0 0 12 12`,version:`1.1`,xmlns:`http://www.w3.org/2000/svg`,"aria-hidden":!0},z(`g`,{stroke:`none`,"stroke-width":`1`,fill:`none`,"fill-rule":`evenodd`},z(`g`,{fill:`currentColor`,"fill-rule":`nonzero`},z(`path`,{d:`M2.08859116,2.2156945 L2.14644661,2.14644661 C2.32001296,1.97288026 2.58943736,1.95359511 2.7843055,2.08859116 L2.85355339,2.14644661 L6,5.293 L9.14644661,2.14644661 C9.34170876,1.95118446 9.65829124,1.95118446 9.85355339,2.14644661 C10.0488155,2.34170876 10.0488155,2.65829124 9.85355339,2.85355339 L6.707,6 L9.85355339,9.14644661 C10.0271197,9.32001296 10.0464049,9.58943736 9.91140884,9.7843055 L9.85355339,9.85355339 C9.67998704,10.0271197 9.41056264,10.0464049 9.2156945,9.91140884 L9.14644661,9.85355339 L6,6.707 L2.85355339,9.85355339 C2.65829124,10.0488155 2.34170876,10.0488155 2.14644661,9.85355339 C1.95118446,9.65829124 1.95118446,9.34170876 2.14644661,9.14644661 L5.293,6 L2.14644661,2.85355339 C1.97288026,2.67998704 1.95359511,2.41056264 2.08859116,2.2156945 L2.14644661,2.14644661 L2.08859116,2.2156945 Z`}))))),Oe=N({name:`Empty`,render(){return z(`svg`,{viewBox:`0 0 28 28`,fill:`none`,xmlns:`http://www.w3.org/2000/svg`},z(`path`,{d:`M26 7.5C26 11.0899 23.0899 14 19.5 14C15.9101 14 13 11.0899 13 7.5C13 3.91015 15.9101 1 19.5 1C23.0899 1 26 3.91015 26 7.5ZM16.8536 4.14645C16.6583 3.95118 16.3417 3.95118 16.1464 4.14645C15.9512 4.34171 15.9512 4.65829 16.1464 4.85355L18.7929 7.5L16.1464 10.1464C15.9512 10.3417 15.9512 10.6583 16.1464 10.8536C16.3417 11.0488 16.6583 11.0488 16.8536 10.8536L19.5 8.20711L22.1464 10.8536C22.3417 11.0488 22.6583 11.0488 22.8536 10.8536C23.0488 10.6583 23.0488 10.3417 22.8536 10.1464L20.2071 7.5L22.8536 4.85355C23.0488 4.65829 23.0488 4.34171 22.8536 4.14645C22.6583 3.95118 22.3417 3.95118 22.1464 4.14645L19.5 6.79289L16.8536 4.14645Z`,fill:`currentColor`}),z(`path`,{d:`M25 22.75V12.5991C24.5572 13.0765 24.053 13.4961 23.5 13.8454V16H17.5L17.3982 16.0068C17.0322 16.0565 16.75 16.3703 16.75 16.75C16.75 18.2688 15.5188 19.5 14 19.5C12.4812 19.5 11.25 18.2688 11.25 16.75L11.2432 16.6482C11.1935 16.2822 10.8797 16 10.5 16H4.5V7.25C4.5 6.2835 5.2835 5.5 6.25 5.5H12.2696C12.4146 4.97463 12.6153 4.47237 12.865 4H6.25C4.45507 4 3 5.45507 3 7.25V22.75C3 24.5449 4.45507 26 6.25 26H21.75C23.5449 26 25 24.5449 25 22.75ZM4.5 22.75V17.5H9.81597L9.85751 17.7041C10.2905 19.5919 11.9808 21 14 21L14.215 20.9947C16.2095 20.8953 17.842 19.4209 18.184 17.5H23.5V22.75C23.5 23.7165 22.7165 24.5 21.75 24.5H6.25C5.2835 24.5 4.5 23.7165 4.5 22.75Z`,fill:`currentColor`}))}}),ke=Q(`base-close`,`
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
`,[Y(`absolute`,`
 height: var(--n-close-icon-size);
 width: var(--n-close-icon-size);
 `),H(`&::before`,`
 content: "";
 position: absolute;
 width: var(--n-close-size);
 height: var(--n-close-size);
 left: 50%;
 top: 50%;
 transform: translateY(-50%) translateX(-50%);
 transition: inherit;
 border-radius: inherit;
 `),L(`disabled`,[H(`&:hover`,`
 color: var(--n-close-icon-color-hover);
 `),H(`&:hover::before`,`
 background-color: var(--n-close-color-hover);
 `),H(`&:focus::before`,`
 background-color: var(--n-close-color-hover);
 `),H(`&:active`,`
 color: var(--n-close-icon-color-pressed);
 `),H(`&:active::before`,`
 background-color: var(--n-close-color-pressed);
 `)]),Y(`disabled`,`
 cursor: not-allowed;
 color: var(--n-close-icon-color-disabled);
 background-color: transparent;
 `),Y(`round`,[H(`&::before`,`
 border-radius: 50%;
 `)])]),Ae=N({name:`BaseClose`,props:{isButtonTag:{type:Boolean,default:!0},clsPrefix:{type:String,required:!0},disabled:{type:Boolean,default:void 0},focusable:{type:Boolean,default:!0},round:Boolean,onClick:Function,absolute:Boolean},setup(e){return S(`-base-close`,ke,J(e,`clsPrefix`)),()=>{let{clsPrefix:t,disabled:n,absolute:r,round:i,isButtonTag:a}=e;return z(a?`button`:`div`,{type:a?`button`:void 0,tabindex:n||!e.focusable?-1:0,"aria-disabled":n,"aria-label":`close`,role:a?void 0:`button`,disabled:n,class:[`${t}-base-close`,r&&`${t}-base-close--absolute`,n&&`${t}-base-close--disabled`,i&&`${t}-base-close--round`],onMousedown:t=>{e.focusable||t.preventDefault()},onClick:e.onClick},z(A,{clsPrefix:t},{default:()=>z(De,null)}))}}});function je(e){return Array.isArray(e)?e:[e]}var Me={STOP:`STOP`};function Ne(e,t){let n=t(e);e.children!==void 0&&n!==Me.STOP&&e.children.forEach(e=>Ne(e,t))}function Pe(e,t={}){let{preserveGroup:n=!1}=t,r=[],i=n?e=>{e.isLeaf||(r.push(e.key),a(e.children))}:e=>{e.isLeaf||(e.isGroup||r.push(e.key),a(e.children))};function a(e){e.forEach(i)}return a(e),r}function Fe(e,t){let{isLeaf:n}=e;return n===void 0?!t(e):n}function Ie(e){return e.children}function Le(e){return e.key}function Re(){return!1}function ze(e,t){let{isLeaf:n}=e;return!(n===!1&&!Array.isArray(t(e)))}function Be(e){return e.disabled===!0}function Ve(e,t){return e.isLeaf===!1&&!Array.isArray(t(e))}function He(e){return e==null?[]:Array.isArray(e)?e:e.checkedKeys??[]}function Ue(e){return e==null||Array.isArray(e)?[]:e.indeterminateKeys??[]}function We(e,t){let n=new Set(e);return t.forEach(e=>{n.has(e)||n.add(e)}),Array.from(n)}function Ge(e,t){let n=new Set(e);return t.forEach(e=>{n.has(e)&&n.delete(e)}),Array.from(n)}function Ke(e){return e?.type===`group`}function qe(e){let t=new Map;return e.forEach((e,n)=>{t.set(e.key,n)}),e=>t.get(e)??null}var Je=class extends Error{constructor(){super(),this.message=`SubtreeNotLoadedError: checking a subtree whose required nodes are not fully loaded.`}};function Ye(e,t,n,r){return $e(t.concat(e),n,r,!1)}function Xe(e,t){let n=new Set;return e.forEach(e=>{let r=t.treeNodeMap.get(e);if(r!==void 0){let e=r.parent;for(;e!==null&&!(e.disabled||n.has(e.key));)n.add(e.key),e=e.parent}}),n}function Ze(e,t,n,r){let i=$e(t,n,r,!1),a=$e(e,n,r,!0),o=Xe(e,n),s=[];return i.forEach(e=>{(a.has(e)||o.has(e))&&s.push(e)}),s.forEach(e=>i.delete(e)),i}function Qe(e,t){let{checkedKeys:n,keysToCheck:r,keysToUncheck:i,indeterminateKeys:a,cascade:o,leafOnly:s,checkStrategy:c,allowNotLoaded:l}=e;if(!o)return r===void 0?i===void 0?{checkedKeys:Array.from(n),indeterminateKeys:Array.from(a)}:{checkedKeys:Ge(n,i),indeterminateKeys:Array.from(a)}:{checkedKeys:We(n,r),indeterminateKeys:Array.from(a)};let{levelTreeNodeMap:u}=t,d;d=i===void 0?r===void 0?$e(n,t,l,!1):Ye(r,n,t,l):Ze(i,n,t,l);let f=c===`parent`,p=c===`child`||s,m=d,h=new Set,g=Math.max.apply(null,Array.from(u.keys()));for(let e=g;e>=0;--e){let t=e===0,n=u.get(e);for(let e of n){if(e.isLeaf)continue;let{key:n,shallowLoaded:r}=e;if(p&&r&&e.children.forEach(e=>{!e.disabled&&!e.isLeaf&&e.shallowLoaded&&m.has(e.key)&&m.delete(e.key)}),e.disabled||!r)continue;let i=!0,a=!1,o=!0;for(let t of e.children){let e=t.key;if(!t.disabled){if(o&&=!1,m.has(e))a=!0;else if(h.has(e)){a=!0,i=!1;break}else if(i=!1,a)break}}i&&!o?(f&&e.children.forEach(e=>{!e.disabled&&m.has(e.key)&&m.delete(e.key)}),m.add(n)):a&&h.add(n),t&&p&&m.has(n)&&m.delete(n)}}return{checkedKeys:Array.from(m),indeterminateKeys:Array.from(h)}}function $e(e,t,n,r){let{treeNodeMap:i,getChildren:a}=t,o=new Set,s=new Set(e);return e.forEach(e=>{let t=i.get(e);t!==void 0&&Ne(t,e=>{if(e.disabled)return Me.STOP;let{key:t}=e;if(!o.has(t)&&(o.add(t),s.add(t),Ve(e.rawNode,a))){if(r)return Me.STOP;if(!n)throw new Je}})}),s}function et(e,{includeGroup:t=!1,includeSelf:n=!0},r){let i=r.treeNodeMap,a=e==null?null:i.get(e)??null,o={keyPath:[],treeNodePath:[],treeNode:a};if(a?.ignored)return o.treeNode=null,o;for(;a;)!a.ignored&&(t||!a.isGroup)&&o.treeNodePath.push(a),a=a.parent;return o.treeNodePath.reverse(),n||o.treeNodePath.pop(),o.keyPath=o.treeNodePath.map(e=>e.key),o}function tt(e){if(e.length===0)return null;let t=e[0];return t.isGroup||t.ignored||t.disabled?t.getNext():t}function nt(e,t){let n=e.siblings,r=n.length,{index:i}=e;return t?n[(i+1)%r]:i===n.length-1?null:n[i+1]}function rt(e,t,{loop:n=!1,includeDisabled:r=!1}={}){let i=t===`prev`?it:nt,a={reverse:t===`prev`},o=!1,s=null;function c(t){if(t!==null){if(t===e){if(!o)o=!0;else if(!e.disabled&&!e.isGroup){s=e;return}}else if((!t.disabled||r)&&!t.ignored&&!t.isGroup){s=t;return}if(t.isGroup){let e=ot(t,a);e===null?c(i(t,n)):s=e}else{let e=i(t,!1);if(e!==null)c(e);else{let e=at(t);e?.isGroup?c(i(e,n)):n&&c(i(t,!0))}}}}return c(e),s}function it(e,t){let n=e.siblings,r=n.length,{index:i}=e;return t?n[(i-1+r)%r]:i===0?null:n[i-1]}function at(e){return e.parent}function ot(e,t={}){let{reverse:n=!1}=t,{children:r}=e;if(r){let{length:e}=r,i=n?e-1:0,a=n?-1:e,o=n?-1:1;for(let e=i;e!==a;e+=o){let n=r[e];if(!n.disabled&&!n.ignored)if(n.isGroup){let e=ot(n,t);if(e!==null)return e}else return n}}return null}var st={getChild(){return this.ignored?null:ot(this)},getParent(){let{parent:e}=this;return e?.isGroup?e.getParent():e},getNext(e={}){return rt(this,`next`,e)},getPrev(e={}){return rt(this,`prev`,e)}};function ct(e,t){let n=t?new Set(t):void 0,r=[];function i(e){e.forEach(e=>{r.push(e),!(e.isLeaf||!e.children||e.ignored)&&(e.isGroup||n===void 0||n.has(e.key))&&i(e.children)})}return i(e),r}function lt(e,t){let n=e.key;for(;t;){if(t.key===n)return!0;t=t.parent}return!1}function ut(e,t,n,r,i,a=null,o=0){let s=[];return e.forEach((c,l)=>{var u;let d=Object.create(r);if(d.rawNode=c,d.siblings=s,d.level=o,d.index=l,d.isFirstChild=l===0,d.isLastChild=l+1===e.length,d.parent=a,!d.ignored){let e=i(c);Array.isArray(e)&&(d.children=ut(e,t,n,r,i,d,o+1))}s.push(d),t.set(d.key,d),n.has(o)||n.set(o,[]),(u=n.get(o))==null||u.push(d)}),s}function dt(e,t={}){let n=new Map,r=new Map,{getDisabled:i=Be,getIgnored:a=Re,getIsGroup:o=Ke,getKey:s=Le}=t,c=t.getChildren??Ie,l=t.ignoreEmptyChildren?e=>{let t=c(e);return Array.isArray(t)?t.length?t:null:t}:c,u=ut(e,n,r,Object.assign({get key(){return s(this.rawNode)},get disabled(){return i(this.rawNode)},get isGroup(){return o(this.rawNode)},get isLeaf(){return Fe(this.rawNode,l)},get shallowLoaded(){return ze(this.rawNode,l)},get ignored(){return a(this.rawNode)},contains(e){return lt(this,e)}},st),l);function d(e){if(e==null)return null;let t=n.get(e);return t&&!t.isGroup&&!t.ignored?t:null}function f(e){if(e==null)return null;let t=n.get(e);return t&&!t.ignored?t:null}function p(e,t){let n=f(e);return n?n.getPrev(t):null}function m(e,t){let n=f(e);return n?n.getNext(t):null}function h(e){let t=f(e);return t?t.getParent():null}function g(e){let t=f(e);return t?t.getChild():null}let _={treeNodes:u,treeNodeMap:n,levelTreeNodeMap:r,maxLevel:Math.max(...r.keys()),getChildren:l,getFlattenedNodes(e){return ct(u,e)},getNode:d,getPrev:p,getNext:m,getParent:h,getChild:g,getFirstAvailableNode(){return tt(u)},getPath(e,t={}){return et(e,t,_)},getCheckedKeys(e,t={}){let{cascade:n=!0,leafOnly:r=!1,checkStrategy:i=`all`,allowNotLoaded:a=!1}=t;return Qe({checkedKeys:He(e),indeterminateKeys:Ue(e),cascade:n,leafOnly:r,checkStrategy:i,allowNotLoaded:a},_)},check(e,t,n={}){let{cascade:r=!0,leafOnly:i=!1,checkStrategy:a=`all`,allowNotLoaded:o=!1}=n;return Qe({checkedKeys:He(t),indeterminateKeys:Ue(t),keysToCheck:e==null?[]:je(e),cascade:r,leafOnly:i,checkStrategy:a,allowNotLoaded:o},_)},uncheck(e,t,n={}){let{cascade:r=!0,leafOnly:i=!1,checkStrategy:a=`all`,allowNotLoaded:o=!1}=n;return Qe({checkedKeys:He(t),indeterminateKeys:Ue(t),keysToUncheck:e==null?[]:je(e),cascade:r,leafOnly:i,checkStrategy:a,allowNotLoaded:o},_)},getNonLeafKeys(e={}){return Pe(u,e)}};return _}var ft=Q(`empty`,`
 display: flex;
 flex-direction: column;
 align-items: center;
 font-size: var(--n-font-size);
`,[j(`icon`,`
 width: var(--n-icon-size);
 height: var(--n-icon-size);
 font-size: var(--n-icon-size);
 line-height: var(--n-icon-size);
 color: var(--n-icon-color);
 transition:
 color .3s var(--n-bezier);
 `,[H(`+`,[j(`description`,`
 margin-top: 8px;
 `)])]),j(`description`,`
 transition: color .3s var(--n-bezier);
 color: var(--n-text-color);
 `),j(`extra`,`
 text-align: center;
 transition: color .3s var(--n-bezier);
 margin-top: 12px;
 color: var(--n-extra-text-color);
 `)]),pt=N({name:`Empty`,props:Object.assign(Object.assign({},X.props),{description:String,showDescription:{type:Boolean,default:!0},showIcon:{type:Boolean,default:!0},size:{type:String,default:`medium`},renderIcon:Function}),slots:Object,setup(e){let{mergedClsPrefixRef:t,inlineThemeDisabled:n,mergedComponentPropsRef:r}=ve(e),i=X(`Empty`,`-empty`,ft,B,e,t),{localeRef:a}=te(`Empty`),o=R(()=>e.description??r?.value?.Empty?.description),s=R(()=>r?.value?.Empty?.renderIcon||(()=>z(Oe,null))),c=R(()=>{let{size:t}=e,{common:{cubicBezierEaseInOut:n},self:{[M(`iconSize`,t)]:r,[M(`fontSize`,t)]:a,textColor:o,iconColor:s,extraTextColor:c}}=i.value;return{"--n-icon-size":r,"--n-font-size":a,"--n-bezier":n,"--n-text-color":o,"--n-icon-color":s,"--n-extra-text-color":c}}),l=n?_(`empty`,R(()=>{let t=``,{size:n}=e;return t+=n[0],t}),c,e):void 0;return{mergedClsPrefix:t,mergedRenderIcon:s,localizedDescription:R(()=>o.value||a.value.description),cssVars:n?void 0:c,themeClass:l?.themeClass,onRender:l?.onRender}},render(){let{$slots:e,mergedClsPrefix:t,onRender:n}=this;return n?.(),z(`div`,{class:[`${t}-empty`,this.themeClass],style:this.cssVars},this.showIcon?z(`div`,{class:`${t}-empty__icon`},e.icon?e.icon():z(A,{clsPrefix:t},{default:this.mergedRenderIcon})):null,this.showDescription?z(`div`,{class:`${t}-empty__description`},e.default?e.default():this.localizedDescription):null,e.extra?z(`div`,{class:`${t}-empty__extra`},e.extra()):null)}}),mt=N({name:`NBaseSelectGroupHeader`,props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(){let{renderLabelRef:e,renderOptionRef:t,labelFieldRef:n,nodePropsRef:r}=se(u);return{labelField:n,nodeProps:r,renderLabel:e,renderOption:t}},render(){let{clsPrefix:e,renderLabel:t,renderOption:n,nodeProps:r,tmNode:{rawNode:i}}=this,a=r?.(i),o=t?t(i,!1):Te(i[this.labelField],i,!1),s=z(`div`,Object.assign({},a,{class:[`${e}-base-select-group-header`,a?.class]}),o);return i.render?i.render({node:s,option:i}):n?n({node:s,option:i,selected:!1}):s}});function ht(e,t){return z(oe,{name:`fade-in-scale-up-transition`},{default:()=>e?z(A,{clsPrefix:t,class:`${t}-base-select-option__check`},{default:()=>z(Ee)}):null})}var gt=N({name:`NBaseSelectOption`,props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(e){let{valueRef:t,pendingTmNodeRef:n,multipleRef:r,valueSetRef:i,renderLabelRef:a,renderOptionRef:o,labelFieldRef:s,valueFieldRef:c,showCheckmarkRef:l,nodePropsRef:d,handleOptionClick:f,handleOptionMouseEnter:p}=se(u),m=W(()=>{let{value:t}=n;return t?e.tmNode.key===t.key:!1});function h(t){let{tmNode:n}=e;n.disabled||f(t,n)}function g(t){let{tmNode:n}=e;n.disabled||p(t,n)}function _(t){let{tmNode:n}=e,{value:r}=m;n.disabled||r||p(t,n)}return{multiple:r,isGrouped:W(()=>{let{tmNode:t}=e,{parent:n}=t;return n&&n.rawNode.type===`group`}),showCheckmark:l,nodeProps:d,isPending:m,isSelected:W(()=>{let{value:n}=t,{value:a}=r;if(n===null)return!1;let o=e.tmNode.rawNode[c.value];if(a){let{value:e}=i;return e.has(o)}else return n===o}),labelField:s,renderLabel:a,renderOption:o,handleMouseMove:_,handleMouseEnter:g,handleClick:h}},render(){let{clsPrefix:e,tmNode:{rawNode:t},isSelected:n,isPending:r,isGrouped:i,showCheckmark:a,nodeProps:o,renderOption:s,renderLabel:c,handleClick:l,handleMouseEnter:u,handleMouseMove:d}=this,f=ht(n,e),p=c?[c(t,n),a&&f]:[Te(t[this.labelField],t,n),a&&f],m=o?.(t),h=z(`div`,Object.assign({},m,{class:[`${e}-base-select-option`,t.class,m?.class,{[`${e}-base-select-option--disabled`]:t.disabled,[`${e}-base-select-option--selected`]:n,[`${e}-base-select-option--grouped`]:i,[`${e}-base-select-option--pending`]:r,[`${e}-base-select-option--show-checkmark`]:a}],style:[m?.style||``,t.style||``],onClick:we([l,m?.onClick]),onMouseenter:we([u,m?.onMouseenter]),onMousemove:we([d,m?.onMousemove])}),z(`div`,{class:`${e}-base-select-option__content`},p));return t.render?t.render({node:h,option:t,selected:n}):s?s({node:h,option:t,selected:n}):h}}),_t=Q(`base-select-menu`,`
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
 `,[j(`content`,`
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
 `),j(`loading, empty`,`
 display: flex;
 padding: 12px 32px;
 flex: 1;
 justify-content: center;
 `),j(`loading`,`
 color: var(--n-loading-color);
 font-size: var(--n-loading-size);
 `),j(`header`,`
 padding: 8px var(--n-option-padding-left);
 font-size: var(--n-option-font-size);
 transition: 
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 border-bottom: 1px solid var(--n-action-divider-color);
 color: var(--n-action-text-color);
 `),j(`action`,`
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
 `,[Y(`show-checkmark`,`
 padding-right: calc(var(--n-option-padding-right) + 20px);
 `),H(`&::before`,`
 content: "";
 position: absolute;
 left: 4px;
 right: 4px;
 top: 0;
 bottom: 0;
 border-radius: var(--n-border-radius);
 transition: background-color .3s var(--n-bezier);
 `),H(`&:active`,`
 color: var(--n-option-text-color-pressed);
 `),Y(`grouped`,`
 padding-left: calc(var(--n-option-padding-left) * 1.5);
 `),Y(`pending`,[H(`&::before`,`
 background-color: var(--n-option-color-pending);
 `)]),Y(`selected`,`
 color: var(--n-option-text-color-active);
 `,[H(`&::before`,`
 background-color: var(--n-option-color-active);
 `),Y(`pending`,[H(`&::before`,`
 background-color: var(--n-option-color-active-pending);
 `)])]),Y(`disabled`,`
 cursor: not-allowed;
 `,[L(`selected`,`
 color: var(--n-option-text-color-disabled);
 `),Y(`selected`,`
 opacity: var(--n-option-opacity-disabled);
 `)]),j(`check`,`
 font-size: 16px;
 position: absolute;
 right: calc(var(--n-option-padding-right) - 4px);
 top: calc(50% - 7px);
 color: var(--n-option-check-color);
 transition: color .3s var(--n-bezier);
 `,[k({enterScale:`0.5`})])])]),vt=N({name:`InternalSelectMenu`,props:Object.assign(Object.assign({},X.props),{clsPrefix:{type:String,required:!0},scrollable:{type:Boolean,default:!0},treeMate:{type:Object,required:!0},multiple:Boolean,size:{type:String,default:`medium`},value:{type:[String,Number,Array],default:null},autoPending:Boolean,virtualScroll:{type:Boolean,default:!0},show:{type:Boolean,default:!0},labelField:{type:String,default:`label`},valueField:{type:String,default:`value`},loading:Boolean,focusable:Boolean,renderLabel:Function,renderOption:Function,nodeProps:Function,showCheckmark:{type:Boolean,default:!0},onMousedown:Function,onScroll:Function,onFocus:Function,onBlur:Function,onKeyup:Function,onKeydown:Function,onTabOut:Function,onMouseenter:Function,onMouseleave:Function,onResize:Function,resetMenuOnOptionsChange:{type:Boolean,default:!0},inlineThemeDisabled:Boolean,scrollbarProps:Object,onToggle:Function}),setup(e){let{mergedClsPrefixRef:t,mergedRtlRef:n,mergedComponentPropsRef:r}=ve(e),i=g(`InternalSelectMenu`,n,t),s=X(`InternalSelectMenu`,`-internal-select-menu`,_t,ue,e,J(e,`clsPrefix`)),c=Z(null),l=Z(null),d=Z(null),f=R(()=>e.treeMate.getFlattenedNodes()),m=R(()=>qe(f.value)),h=Z(null);function v(){let{treeMate:t}=e,n=null,{value:r}=e;r===null?n=t.getFirstAvailableNode():(n=e.multiple?t.getNode((r||[])[(r||[]).length-1]):t.getNode(r),(!n||n.disabled)&&(n=t.getFirstAvailableNode())),P(n||null)}function y(){let{value:t}=h;t&&!e.treeMate.getNode(t.key)&&(h.value=null)}let b;ge(()=>e.show,t=>{t?b=ge(()=>e.treeMate,()=>{e.resetMenuOnOptionsChange?(e.autoPending?v():y(),le(F)):y()},{immediate:!0}):b?.()},{immediate:!0}),_e(()=>{b?.()});let x=R(()=>p(s.value.self[M(`optionHeight`,e.size)])),S=R(()=>a(s.value.self[M(`padding`,e.size)])),C=R(()=>e.multiple&&Array.isArray(e.value)?new Set(e.value):new Set),w=R(()=>{let e=f.value;return e&&e.length===0}),ee=R(()=>r?.value?.Select?.renderEmpty);function te(t){let{onToggle:n}=e;n&&n(t)}function T(t){let{onScroll:n}=e;n&&n(t)}function D(e){var t;(t=d.value)==null||t.sync(),T(e)}function O(){var e;(e=d.value)==null||e.sync()}function ne(){let{value:e}=h;return e||null}function k(e,t){t.disabled||P(t,!1)}function A(e,t){t.disabled||te(t)}function re(t){var n;E(t,`action`)||(n=e.onKeyup)==null||n.call(e,t)}function ie(t){var n;E(t,`action`)||(n=e.onKeydown)==null||n.call(e,t)}function ae(t){var n;(n=e.onMousedown)==null||n.call(e,t),!e.focusable&&t.preventDefault()}function j(){let{value:e}=h;e&&P(e.getNext({loop:!0}),!0)}function N(){let{value:e}=h;e&&P(e.getPrev({loop:!0}),!0)}function P(e,t=!1){h.value=e,t&&F()}function F(){var t,n;let r=h.value;if(!r)return;let i=m.value(r.key);i!==null&&(e.virtualScroll?(t=l.value)==null||t.scrollTo({index:i}):(n=d.value)==null||n.scrollTo({index:i,elSize:x.value}))}function oe(t){var n;c.value?.contains(t.target)&&((n=e.onFocus)==null||n.call(e,t))}function I(t){var n;c.value?.contains(t.relatedTarget)||(n=e.onBlur)==null||n.call(e,t)}K(u,{handleOptionMouseEnter:k,handleOptionClick:A,valueSetRef:C,pendingTmNodeRef:h,nodePropsRef:J(e,`nodeProps`),showCheckmarkRef:J(e,`showCheckmark`),multipleRef:J(e,`multiple`),valueRef:J(e,`value`),renderLabelRef:J(e,`renderLabel`),renderOptionRef:J(e,`renderOption`),labelFieldRef:J(e,`labelField`),valueFieldRef:J(e,`valueField`)}),K(o,c),ce(()=>{let{value:e}=d;e&&e.sync()});let L=R(()=>{let{size:t}=e,{common:{cubicBezierEaseInOut:n},self:{height:r,borderRadius:i,color:o,groupHeaderTextColor:c,actionDividerColor:l,optionTextColorPressed:u,optionTextColor:d,optionTextColorDisabled:f,optionTextColorActive:p,optionOpacityDisabled:m,optionCheckColor:h,actionTextColor:g,optionColorPending:_,optionColorActive:v,loadingColor:y,loadingSize:b,optionColorActivePending:x,[M(`optionFontSize`,t)]:S,[M(`optionHeight`,t)]:C,[M(`optionPadding`,t)]:w}}=s.value;return{"--n-height":r,"--n-action-divider-color":l,"--n-action-text-color":g,"--n-bezier":n,"--n-border-radius":i,"--n-color":o,"--n-option-font-size":S,"--n-group-header-text-color":c,"--n-option-check-color":h,"--n-option-color-pending":_,"--n-option-color-active":v,"--n-option-color-active-pending":x,"--n-option-height":C,"--n-option-opacity-disabled":m,"--n-option-text-color":d,"--n-option-text-color-active":p,"--n-option-text-color-disabled":f,"--n-option-text-color-pressed":u,"--n-option-padding":w,"--n-option-padding-left":a(w,`left`),"--n-option-padding-right":a(w,`right`),"--n-loading-color":y,"--n-loading-size":b}}),{inlineThemeDisabled:z}=e,se=z?_(`internal-select-menu`,R(()=>e.size[0]),L,e):void 0,B={selfRef:c,next:j,prev:N,getPendingTmNode:ne};return Se(c,e.onResize),Object.assign({mergedTheme:s,mergedClsPrefix:t,rtlEnabled:i,virtualListRef:l,scrollbarRef:d,itemSize:x,padding:S,flattenedNodes:f,empty:w,mergedRenderEmpty:ee,virtualListContainer(){let{value:e}=l;return e?.listElRef},virtualListContent(){let{value:e}=l;return e?.itemsElRef},doScroll:T,handleFocusin:oe,handleFocusout:I,handleKeyUp:re,handleKeyDown:ie,handleMouseDown:ae,handleVirtualListResize:O,handleVirtualListScroll:D,cssVars:z?void 0:L,themeClass:se?.themeClass,onRender:se?.onRender},B)},render(){let{$slots:e,virtualScroll:t,clsPrefix:n,mergedTheme:r,themeClass:i,onRender:a}=this;return a?.(),z(`div`,{ref:`selfRef`,tabindex:this.focusable?0:-1,class:[`${n}-base-select-menu`,`${n}-base-select-menu--${this.size}-size`,this.rtlEnabled&&`${n}-base-select-menu--rtl`,i,this.multiple&&`${n}-base-select-menu--multiple`],style:this.cssVars,onFocusin:this.handleFocusin,onFocusout:this.handleFocusout,onKeyup:this.handleKeyUp,onKeydown:this.handleKeyDown,onMousedown:this.handleMouseDown,onMouseenter:this.onMouseenter,onMouseleave:this.onMouseleave},C(e.header,e=>e&&z(`div`,{class:`${n}-base-select-menu__header`,"data-header":!0,key:`header`},e)),this.loading?z(`div`,{class:`${n}-base-select-menu__loading`},z(x,{clsPrefix:n,strokeWidth:20})):this.empty?z(`div`,{class:`${n}-base-select-menu__empty`,"data-empty":!0},w(e.empty,()=>[this.mergedRenderEmpty?.call(this)||z(pt,{theme:r.peers.Empty,themeOverrides:r.peerOverrides.Empty,size:this.size})])):z(h,Object.assign({ref:`scrollbarRef`,theme:r.peers.Scrollbar,themeOverrides:r.peerOverrides.Scrollbar,scrollable:this.scrollable,container:t?this.virtualListContainer:void 0,content:t?this.virtualListContent:void 0,onScroll:t?void 0:this.doScroll},this.scrollbarProps),{default:()=>t?z(T,{ref:`virtualListRef`,class:`${n}-virtual-list`,items:this.flattenedNodes,itemSize:this.itemSize,showScrollbar:!1,paddingTop:this.padding.top,paddingBottom:this.padding.bottom,onResize:this.handleVirtualListResize,onScroll:this.handleVirtualListScroll,itemResizable:!0},{default:({item:e})=>e.isGroup?z(mt,{key:e.key,clsPrefix:n,tmNode:e}):e.ignored?null:z(gt,{clsPrefix:n,key:e.key,tmNode:e})}):z(`div`,{class:`${n}-base-select-menu-option-wrapper`,style:{paddingTop:this.padding.top,paddingBottom:this.padding.bottom}},this.flattenedNodes.map(e=>e.isGroup?z(mt,{key:e.key,clsPrefix:n,tmNode:e}):z(gt,{clsPrefix:n,key:e.key,tmNode:e})))}),C(e.action,e=>e&&[z(`div`,{class:`${n}-base-select-menu__action`,"data-action":!0,key:`action`},e),z(D,{onFocus:this.onTabOut,key:`focus-detector`})]))}});function yt(e){let{textColor2:t,primaryColorHover:n,primaryColorPressed:r,primaryColor:i,infoColor:a,successColor:o,warningColor:s,errorColor:c,baseColor:l,borderColor:u,opacityDisabled:d,tagColor:f,closeIconColor:p,closeIconColorHover:m,closeIconColorPressed:h,borderRadiusSmall:g,fontSizeMini:_,fontSizeTiny:v,fontSizeSmall:y,fontSizeMedium:b,heightMini:x,heightTiny:S,heightSmall:C,heightMedium:w,closeColorHover:ee,closeColorPressed:te,buttonColor2Hover:T,buttonColor2Pressed:E,fontWeightStrong:D}=e;return Object.assign(Object.assign({},q),{closeBorderRadius:g,heightTiny:x,heightSmall:S,heightMedium:C,heightLarge:w,borderRadius:g,opacityDisabled:d,fontSizeTiny:_,fontSizeSmall:v,fontSizeMedium:y,fontSizeLarge:b,fontWeightStrong:D,textColorCheckable:t,textColorHoverCheckable:t,textColorPressedCheckable:t,textColorChecked:l,colorCheckable:`#0000`,colorHoverCheckable:T,colorPressedCheckable:E,colorChecked:i,colorCheckedHover:n,colorCheckedPressed:r,border:`1px solid ${u}`,textColor:t,color:f,colorBordered:`rgb(250, 250, 252)`,closeIconColor:p,closeIconColorHover:m,closeIconColorPressed:h,closeColorHover:ee,closeColorPressed:te,borderPrimary:`1px solid ${V(i,{alpha:.3})}`,textColorPrimary:i,colorPrimary:V(i,{alpha:.12}),colorBorderedPrimary:V(i,{alpha:.1}),closeIconColorPrimary:i,closeIconColorHoverPrimary:i,closeIconColorPressedPrimary:i,closeColorHoverPrimary:V(i,{alpha:.12}),closeColorPressedPrimary:V(i,{alpha:.18}),borderInfo:`1px solid ${V(a,{alpha:.3})}`,textColorInfo:a,colorInfo:V(a,{alpha:.12}),colorBorderedInfo:V(a,{alpha:.1}),closeIconColorInfo:a,closeIconColorHoverInfo:a,closeIconColorPressedInfo:a,closeColorHoverInfo:V(a,{alpha:.12}),closeColorPressedInfo:V(a,{alpha:.18}),borderSuccess:`1px solid ${V(o,{alpha:.3})}`,textColorSuccess:o,colorSuccess:V(o,{alpha:.12}),colorBorderedSuccess:V(o,{alpha:.1}),closeIconColorSuccess:o,closeIconColorHoverSuccess:o,closeIconColorPressedSuccess:o,closeColorHoverSuccess:V(o,{alpha:.12}),closeColorPressedSuccess:V(o,{alpha:.18}),borderWarning:`1px solid ${V(s,{alpha:.35})}`,textColorWarning:s,colorWarning:V(s,{alpha:.15}),colorBorderedWarning:V(s,{alpha:.12}),closeIconColorWarning:s,closeIconColorHoverWarning:s,closeIconColorPressedWarning:s,closeColorHoverWarning:V(s,{alpha:.12}),closeColorPressedWarning:V(s,{alpha:.18}),borderError:`1px solid ${V(c,{alpha:.23})}`,textColorError:c,colorError:V(c,{alpha:.1}),colorBorderedError:V(c,{alpha:.08}),closeIconColorError:c,closeIconColorHoverError:c,closeIconColorPressedError:c,closeColorHoverError:V(c,{alpha:.12}),closeColorPressedError:V(c,{alpha:.18})})}var bt={name:`Tag`,common:ye,self:yt},xt={color:Object,type:{type:String,default:`default`},round:Boolean,size:String,closable:Boolean,disabled:{type:Boolean,default:void 0}},St=Q(`tag`,`
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
`,[Y(`strong`,`
 font-weight: var(--n-font-weight-strong);
 `),j(`border`,`
 pointer-events: none;
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 border-radius: inherit;
 border: var(--n-border);
 transition: border-color .3s var(--n-bezier);
 `),j(`icon`,`
 display: flex;
 margin: 0 4px 0 0;
 color: var(--n-text-color);
 transition: color .3s var(--n-bezier);
 font-size: var(--n-avatar-size-override);
 `),j(`avatar`,`
 display: flex;
 margin: 0 6px 0 0;
 `),j(`close`,`
 margin: var(--n-close-margin);
 transition:
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 `),Y(`round`,`
 padding: 0 calc(var(--n-height) / 3);
 border-radius: calc(var(--n-height) / 2);
 `,[j(`icon`,`
 margin: 0 4px 0 calc((var(--n-height) - 8px) / -2);
 `),j(`avatar`,`
 margin: 0 6px 0 calc((var(--n-height) - 8px) / -2);
 `),Y(`closable`,`
 padding: 0 calc(var(--n-height) / 4) 0 calc(var(--n-height) / 3);
 `)]),Y(`icon, avatar`,[Y(`round`,`
 padding: 0 calc(var(--n-height) / 3) 0 calc(var(--n-height) / 2);
 `)]),Y(`disabled`,`
 cursor: not-allowed !important;
 opacity: var(--n-opacity-disabled);
 `),Y(`checkable`,`
 cursor: pointer;
 box-shadow: none;
 color: var(--n-text-color-checkable);
 background-color: var(--n-color-checkable);
 `,[L(`disabled`,[H(`&:hover`,`background-color: var(--n-color-hover-checkable);`,[L(`checked`,`color: var(--n-text-color-hover-checkable);`)]),H(`&:active`,`background-color: var(--n-color-pressed-checkable);`,[L(`checked`,`color: var(--n-text-color-pressed-checkable);`)])]),Y(`checked`,`
 color: var(--n-text-color-checked);
 background-color: var(--n-color-checked);
 `,[L(`disabled`,[H(`&:hover`,`background-color: var(--n-color-checked-hover);`),H(`&:active`,`background-color: var(--n-color-checked-pressed);`)])])])]),Ct=Object.assign(Object.assign(Object.assign({},X.props),xt),{bordered:{type:Boolean,default:void 0},checked:Boolean,checkable:Boolean,strong:Boolean,triggerClickOnClose:Boolean,onClose:[Array,Function],onMouseenter:Function,onMouseleave:Function,"onUpdate:checked":Function,onUpdateChecked:Function,internalCloseFocusable:{type:Boolean,default:!0},internalCloseIsButtonTag:{type:Boolean,default:!0},onCheckedChange:Function}),wt=G(`n-tag`),Tt=N({name:`Tag`,props:Ct,slots:Object,setup(e){let t=Z(null),{mergedBorderedRef:r,mergedClsPrefixRef:i,inlineThemeDisabled:o,mergedRtlRef:s,mergedComponentPropsRef:c}=ve(e),l=R(()=>e.size||c?.value?.Tag?.size||`medium`),u=X(`Tag`,`-tag`,St,bt,e,i);K(wt,{roundRef:J(e,`round`)});function f(){if(!e.disabled&&e.checkable){let{checked:t,onCheckedChange:n,onUpdateChecked:r,"onUpdate:checked":i}=e;r&&r(!t),i&&i(!t),n&&n(!t)}}function p(t){if(e.triggerClickOnClose||t.stopPropagation(),!e.disabled){let{onClose:n}=e;n&&d(n,t)}}let m={setTextContent(e){let{value:n}=t;n&&(n.textContent=e)}},h=g(`Tag`,s,i),v=R(()=>{let{type:t,color:{color:n,textColor:i}={}}=e,o=l.value,{common:{cubicBezierEaseInOut:s},self:{padding:c,closeMargin:d,borderRadius:f,opacityDisabled:p,textColorCheckable:m,textColorHoverCheckable:h,textColorPressedCheckable:g,textColorChecked:_,colorCheckable:v,colorHoverCheckable:y,colorPressedCheckable:b,colorChecked:x,colorCheckedHover:S,colorCheckedPressed:C,closeBorderRadius:w,fontWeightStrong:ee,[M(`colorBordered`,t)]:te,[M(`closeSize`,o)]:T,[M(`closeIconSize`,o)]:E,[M(`fontSize`,o)]:D,[M(`height`,o)]:O,[M(`color`,t)]:ne,[M(`textColor`,t)]:k,[M(`border`,t)]:A,[M(`closeIconColor`,t)]:re,[M(`closeIconColorHover`,t)]:ie,[M(`closeIconColorPressed`,t)]:ae,[M(`closeColorHover`,t)]:j,[M(`closeColorPressed`,t)]:N}}=u.value,P=a(d);return{"--n-font-weight-strong":ee,"--n-avatar-size-override":`calc(${O} - 8px)`,"--n-bezier":s,"--n-border-radius":f,"--n-border":A,"--n-close-icon-size":E,"--n-close-color-pressed":N,"--n-close-color-hover":j,"--n-close-border-radius":w,"--n-close-icon-color":re,"--n-close-icon-color-hover":ie,"--n-close-icon-color-pressed":ae,"--n-close-icon-color-disabled":re,"--n-close-margin-top":P.top,"--n-close-margin-right":P.right,"--n-close-margin-bottom":P.bottom,"--n-close-margin-left":P.left,"--n-close-size":T,"--n-color":n||(r.value?te:ne),"--n-color-checkable":v,"--n-color-checked":x,"--n-color-checked-hover":S,"--n-color-checked-pressed":C,"--n-color-hover-checkable":y,"--n-color-pressed-checkable":b,"--n-font-size":D,"--n-height":O,"--n-opacity-disabled":p,"--n-padding":c,"--n-text-color":i||k,"--n-text-color-checkable":m,"--n-text-color-checked":_,"--n-text-color-hover-checkable":h,"--n-text-color-pressed-checkable":g}}),y=o?_(`tag`,R(()=>{let t=``,{type:i,color:{color:a,textColor:o}={}}=e;return t+=i[0],t+=l.value[0],a&&(t+=`a${n(a)}`),o&&(t+=`b${n(o)}`),r.value&&(t+=`c`),t}),v,e):void 0;return Object.assign(Object.assign({},m),{rtlEnabled:h,mergedClsPrefix:i,contentRef:t,mergedBordered:r,handleClick:f,handleCloseClick:p,cssVars:o?void 0:v,themeClass:y?.themeClass,onRender:y?.onRender})},render(){var e;let{mergedClsPrefix:t,rtlEnabled:n,closable:r,color:{borderColor:i}={},round:a,onRender:o,$slots:s}=this;o?.();let c=C(s.avatar,e=>e&&z(`div`,{class:`${t}-tag__avatar`},e)),l=C(s.icon,e=>e&&z(`div`,{class:`${t}-tag__icon`},e));return z(`div`,{class:[`${t}-tag`,this.themeClass,{[`${t}-tag--rtl`]:n,[`${t}-tag--strong`]:this.strong,[`${t}-tag--disabled`]:this.disabled,[`${t}-tag--checkable`]:this.checkable,[`${t}-tag--checked`]:this.checkable&&this.checked,[`${t}-tag--round`]:a,[`${t}-tag--avatar`]:c,[`${t}-tag--icon`]:l,[`${t}-tag--closable`]:r}],style:this.cssVars,onClick:this.handleClick,onMouseenter:this.onMouseenter,onMouseleave:this.onMouseleave},l||c,z(`span`,{class:`${t}-tag__content`,ref:`contentRef`},(e=this.$slots).default?.call(e)),!this.checkable&&r?z(Ae,{clsPrefix:t,class:`${t}-tag__close`,disabled:this.disabled,onClick:this.handleCloseClick,focusable:this.internalCloseFocusable,round:a,isButtonTag:this.internalCloseIsButtonTag,absolute:!0}):null,!this.checkable&&this.mergedBordered?z(`div`,{class:`${t}-tag__border`,style:{borderColor:i}}):null)}}),Et=H([Q(`base-selection`,`
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
 `),Q(`base-selection-tags`,`min-height: var(--n-height);`),j(`border, state-border`,`
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
 `),j(`state-border`,`
 z-index: 1;
 border-color: #0000;
 `),Q(`base-suffix`,`
 cursor: pointer;
 position: absolute;
 top: 50%;
 transform: translateY(-50%);
 right: 10px;
 `,[j(`arrow`,`
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
 `,[j(`wrapper`,`
 flex-basis: 0;
 flex-grow: 1;
 overflow: hidden;
 text-overflow: ellipsis;
 `)]),Q(`base-selection-placeholder`,`
 color: var(--n-placeholder-color);
 `,[j(`inner`,`
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
 `,[j(`content`,`
 text-overflow: ellipsis;
 overflow: hidden;
 white-space: nowrap; 
 `)]),j(`render-label`,`
 color: var(--n-text-color);
 `)]),L(`disabled`,[H(`&:hover`,[j(`state-border`,`
 box-shadow: var(--n-box-shadow-hover);
 border: var(--n-border-hover);
 `)]),Y(`focus`,[j(`state-border`,`
 box-shadow: var(--n-box-shadow-focus);
 border: var(--n-border-focus);
 `)]),Y(`active`,[j(`state-border`,`
 box-shadow: var(--n-box-shadow-active);
 border: var(--n-border-active);
 `),Q(`base-selection-label`,`background-color: var(--n-color-active);`),Q(`base-selection-tags`,`background-color: var(--n-color-active);`)])]),Y(`disabled`,`cursor: not-allowed;`,[j(`arrow`,`
 color: var(--n-arrow-color-disabled);
 `),Q(`base-selection-label`,`
 cursor: not-allowed;
 background-color: var(--n-color-disabled);
 `,[Q(`base-selection-input`,`
 cursor: not-allowed;
 color: var(--n-text-color-disabled);
 `),j(`render-label`,`
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
 `,[j(`input`,`
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
 `),j(`mirror`,`
 position: absolute;
 left: 0;
 top: 0;
 white-space: pre;
 visibility: hidden;
 user-select: none;
 -webkit-user-select: none;
 opacity: 0;
 `)]),[`warning`,`error`].map(e=>Y(`${e}-status`,[j(`state-border`,`border: var(--n-border-${e});`),L(`disabled`,[H(`&:hover`,[j(`state-border`,`
 box-shadow: var(--n-box-shadow-hover-${e});
 border: var(--n-border-hover-${e});
 `)]),Y(`active`,[j(`state-border`,`
 box-shadow: var(--n-box-shadow-active-${e});
 border: var(--n-border-active-${e});
 `),Q(`base-selection-label`,`background-color: var(--n-color-active-${e});`),Q(`base-selection-tags`,`background-color: var(--n-color-active-${e});`)]),Y(`focus`,[j(`state-border`,`
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
 `,[H(`&:last-child`,`padding-right: 0;`),Q(`tag`,`
 font-size: 14px;
 max-width: 100%;
 `,[j(`content`,`
 line-height: 1.25;
 text-overflow: ellipsis;
 overflow: hidden;
 `)])])]),Dt=N({name:`InternalSelection`,props:Object.assign(Object.assign({},X.props),{clsPrefix:{type:String,required:!0},bordered:{type:Boolean,default:void 0},active:Boolean,pattern:{type:String,default:``},placeholder:String,selectedOption:{type:Object,default:null},selectedOptions:{type:Array,default:null},labelField:{type:String,default:`label`},valueField:{type:String,default:`value`},multiple:Boolean,filterable:Boolean,clearable:Boolean,disabled:Boolean,size:{type:String,default:`medium`},loading:Boolean,autofocus:Boolean,showArrow:{type:Boolean,default:!0},inputProps:Object,focused:Boolean,renderTag:Function,onKeydown:Function,onClick:Function,onBlur:Function,onFocus:Function,onDeleteOption:Function,maxTagCount:[String,Number],ellipsisTagPopoverProps:Object,onClear:Function,onPatternInput:Function,onPatternFocus:Function,onPatternBlur:Function,renderLabel:Function,status:String,inlineThemeDisabled:Boolean,ignoreComposition:{type:Boolean,default:!0},onResize:Function}),setup(e){let{mergedClsPrefixRef:t,mergedRtlRef:n}=ve(e),r=g(`InternalSelection`,n,t),i=Z(null),o=Z(null),s=Z(null),c=Z(null),l=Z(null),u=Z(null),d=Z(null),f=Z(null),p=Z(null),m=Z(null),h=Z(!1),v=Z(!1),y=Z(!1),b=X(`InternalSelection`,`-internal-selection`,Et,he,e,J(e,`clsPrefix`)),x=R(()=>e.clearable&&!e.disabled&&(y.value||e.active)),S=R(()=>e.selectedOption?e.renderTag?e.renderTag({option:e.selectedOption,handleClose:()=>{}}):e.renderLabel?e.renderLabel(e.selectedOption,!0):Te(e.selectedOption[e.labelField],e.selectedOption,!0):e.placeholder),C=R(()=>{let t=e.selectedOption;if(t)return t[e.labelField]}),w=R(()=>e.multiple?!!(Array.isArray(e.selectedOptions)&&e.selectedOptions.length):e.selectedOption!==null);function ee(){var t;let{value:n}=i;if(n){let{value:r}=o;r&&(r.style.width=`${n.offsetWidth}px`,e.maxTagCount!==`responsive`&&((t=p.value)==null||t.sync({showAllItemsBeforeCalculate:!1})))}}function te(){let{value:e}=m;e&&(e.style.display=`none`)}function T(){let{value:e}=m;e&&(e.style.display=`inline-block`)}ge(J(e,`active`),e=>{e||te()}),ge(J(e,`pattern`),()=>{e.multiple&&le(ee)});function E(t){let{onFocus:n}=e;n&&n(t)}function D(t){let{onBlur:n}=e;n&&n(t)}function O(t){let{onDeleteOption:n}=e;n&&n(t)}function ne(t){let{onClear:n}=e;n&&n(t)}function k(t){let{onPatternInput:n}=e;n&&n(t)}function A(e){(!e.relatedTarget||!s.value?.contains(e.relatedTarget))&&E(e)}function re(e){s.value?.contains(e.relatedTarget)||D(e)}function ie(e){ne(e)}function ae(){y.value=!0}function j(){y.value=!1}function N(t){!e.active||!e.filterable||t.target!==o.value&&t.preventDefault()}function P(e){O(e)}let F=Z(!1);function oe(t){if(t.key===`Backspace`&&!F.value&&!e.pattern.length){let{selectedOptions:t}=e;t?.length&&P(t[t.length-1])}}let I=null;function L(t){let{value:n}=i;n&&(n.textContent=t.target.value,ee()),e.ignoreComposition&&F.value?I=t:k(t)}function z(){F.value=!0}function se(){F.value=!1,e.ignoreComposition&&k(I),I=null}function B(t){var n;v.value=!0,(n=e.onPatternFocus)==null||n.call(e,t)}function V(t){var n;v.value=!1,(n=e.onPatternBlur)==null||n.call(e,t)}function H(){var t,n;if(e.filterable)v.value=!1,(t=u.value)==null||t.blur(),(n=o.value)==null||n.blur();else if(e.multiple){let{value:e}=c;e?.blur()}else{let{value:e}=l;e?.blur()}}function U(){var t,n,r;e.filterable?(v.value=!1,(t=u.value)==null||t.focus()):e.multiple?(n=c.value)==null||n.focus():(r=l.value)==null||r.focus()}function ue(){let{value:e}=o;e&&(T(),e.focus())}function de(){let{value:e}=o;e&&e.blur()}function W(e){let{value:t}=d;t&&t.setTextContent(`+${e}`)}function G(){let{value:e}=f;return e}function fe(){return o.value}let K=null;function q(){K!==null&&window.clearTimeout(K)}function me(){e.active||(q(),K=window.setTimeout(()=>{w.value&&(h.value=!0)},100))}function _e(){q()}function Y(e){e||(q(),h.value=!1)}ge(w,e=>{e||(h.value=!1)}),ce(()=>{pe(()=>{let t=u.value;t&&(e.disabled?t.removeAttribute(`tabindex`):t.tabIndex=v.value?-1:0)})}),Se(s,e.onResize);let{inlineThemeDisabled:Q}=e,ye=R(()=>{let{size:t}=e,{common:{cubicBezierEaseInOut:n},self:{fontWeight:r,borderRadius:i,color:o,placeholderColor:s,textColor:c,paddingSingle:l,paddingMultiple:u,caretColor:d,colorDisabled:f,textColorDisabled:p,placeholderColorDisabled:m,colorActive:h,boxShadowFocus:g,boxShadowActive:_,boxShadowHover:v,border:y,borderFocus:x,borderHover:S,borderActive:C,arrowColor:w,arrowColorDisabled:ee,loadingColor:te,colorActiveWarning:T,boxShadowFocusWarning:E,boxShadowActiveWarning:D,boxShadowHoverWarning:O,borderWarning:ne,borderFocusWarning:k,borderHoverWarning:A,borderActiveWarning:re,colorActiveError:ie,boxShadowFocusError:ae,boxShadowActiveError:j,boxShadowHoverError:N,borderError:P,borderFocusError:F,borderHoverError:oe,borderActiveError:I,clearColor:L,clearColorHover:R,clearColorPressed:z,clearSize:se,arrowSize:B,[M(`height`,t)]:V,[M(`fontSize`,t)]:ce}}=b.value,H=a(l),U=a(u);return{"--n-bezier":n,"--n-border":y,"--n-border-active":C,"--n-border-focus":x,"--n-border-hover":S,"--n-border-radius":i,"--n-box-shadow-active":_,"--n-box-shadow-focus":g,"--n-box-shadow-hover":v,"--n-caret-color":d,"--n-color":o,"--n-color-active":h,"--n-color-disabled":f,"--n-font-size":ce,"--n-height":V,"--n-padding-single-top":H.top,"--n-padding-multiple-top":U.top,"--n-padding-single-right":H.right,"--n-padding-multiple-right":U.right,"--n-padding-single-left":H.left,"--n-padding-multiple-left":U.left,"--n-padding-single-bottom":H.bottom,"--n-padding-multiple-bottom":U.bottom,"--n-placeholder-color":s,"--n-placeholder-color-disabled":m,"--n-text-color":c,"--n-text-color-disabled":p,"--n-arrow-color":w,"--n-arrow-color-disabled":ee,"--n-loading-color":te,"--n-color-active-warning":T,"--n-box-shadow-focus-warning":E,"--n-box-shadow-active-warning":D,"--n-box-shadow-hover-warning":O,"--n-border-warning":ne,"--n-border-focus-warning":k,"--n-border-hover-warning":A,"--n-border-active-warning":re,"--n-color-active-error":ie,"--n-box-shadow-focus-error":ae,"--n-box-shadow-active-error":j,"--n-box-shadow-hover-error":N,"--n-border-error":P,"--n-border-focus-error":F,"--n-border-hover-error":oe,"--n-border-active-error":I,"--n-clear-size":se,"--n-clear-color":L,"--n-clear-color-hover":R,"--n-clear-color-pressed":z,"--n-arrow-size":B,"--n-font-weight":r}}),$=Q?_(`internal-selection`,R(()=>e.size[0]),ye,e):void 0;return{mergedTheme:b,mergedClearable:x,mergedClsPrefix:t,rtlEnabled:r,patternInputFocused:v,filterablePlaceholder:S,label:C,selected:w,showTagsPanel:h,isComposing:F,counterRef:d,counterWrapperRef:f,patternInputMirrorRef:i,patternInputRef:o,selfRef:s,multipleElRef:c,singleElRef:l,patternInputWrapperRef:u,overflowRef:p,inputTagElRef:m,handleMouseDown:N,handleFocusin:A,handleClear:ie,handleMouseEnter:ae,handleMouseLeave:j,handleDeleteOption:P,handlePatternKeyDown:oe,handlePatternInputInput:L,handlePatternInputBlur:V,handlePatternInputFocus:B,handleMouseEnterCounter:me,handleMouseLeaveCounter:_e,handleFocusout:re,handleCompositionEnd:se,handleCompositionStart:z,onPopoverUpdateShow:Y,focus:U,focusInput:ue,blur:H,blurInput:de,updateCounter:W,getCounter:G,getTail:fe,renderLabel:e.renderLabel,cssVars:Q?void 0:ye,themeClass:$?.themeClass,onRender:$?.onRender}},render(){let{status:e,multiple:t,size:n,disabled:r,filterable:i,maxTagCount:a,bordered:o,clsPrefix:s,ellipsisTagPopoverProps:c,onRender:l,renderTag:u,renderLabel:d}=this;l?.();let f=a===`responsive`,p=typeof a==`number`,h=f||p,g=z(m,null,{default:()=>z(O,{clsPrefix:s,loading:this.loading,showArrow:this.showArrow,showClear:this.mergedClearable&&this.selected,onClear:this.handleClear},{default:()=>{var e;return(e=this.$slots).arrow?.call(e)}})}),_;if(t){let{labelField:e}=this,t=t=>z(`div`,{class:`${s}-base-selection-tag-wrapper`,key:t.value},u?u({option:t,handleClose:()=>{this.handleDeleteOption(t)}}):z(Tt,{size:n,closable:!t.disabled,disabled:r,onClose:()=>{this.handleDeleteOption(t)},internalCloseIsButtonTag:!1,internalCloseFocusable:!1},{default:()=>d?d(t,!0):Te(t[e],t,!0)})),o=()=>(p?this.selectedOptions.slice(0,a):this.selectedOptions).map(t),l=i?z(`div`,{class:`${s}-base-selection-input-tag`,ref:`inputTagElRef`,key:`__input-tag__`},z(`input`,Object.assign({},this.inputProps,{ref:`patternInputRef`,tabindex:-1,disabled:r,value:this.pattern,autofocus:this.autofocus,class:`${s}-base-selection-input-tag__input`,onBlur:this.handlePatternInputBlur,onFocus:this.handlePatternInputFocus,onKeydown:this.handlePatternKeyDown,onInput:this.handlePatternInputInput,onCompositionstart:this.handleCompositionStart,onCompositionend:this.handleCompositionEnd})),z(`span`,{ref:`patternInputMirrorRef`,class:`${s}-base-selection-input-tag__mirror`},this.pattern)):null,m=f?()=>z(`div`,{class:`${s}-base-selection-tag-wrapper`,ref:`counterWrapperRef`},z(Tt,{size:n,ref:`counterRef`,onMouseenter:this.handleMouseEnterCounter,onMouseleave:this.handleMouseLeaveCounter,disabled:r})):void 0,v;if(p){let e=this.selectedOptions.length-a;e>0&&(v=z(`div`,{class:`${s}-base-selection-tag-wrapper`,key:`__counter__`},z(Tt,{size:n,ref:`counterRef`,onMouseenter:this.handleMouseEnterCounter,disabled:r},{default:()=>`+${e}`})))}let y=f?i?z(xe,{ref:`overflowRef`,updateCounter:this.updateCounter,getCounter:this.getCounter,getTail:this.getTail,style:{width:`100%`,display:`flex`,overflow:`hidden`}},{default:o,counter:m,tail:()=>l}):z(xe,{ref:`overflowRef`,updateCounter:this.updateCounter,getCounter:this.getCounter,style:{width:`100%`,display:`flex`,overflow:`hidden`}},{default:o,counter:m}):p&&v?o().concat(v):o(),b=h?()=>z(`div`,{class:`${s}-base-selection-popover`},f?o():this.selectedOptions.map(t)):void 0,x=h?Object.assign({show:this.showTagsPanel,trigger:`hover`,overlap:!0,placement:`top`,width:`trigger`,onUpdateShow:this.onPopoverUpdateShow,theme:this.mergedTheme.peers.Popover,themeOverrides:this.mergedTheme.peerOverrides.Popover},c):null,S=!this.selected&&(!this.active||!this.pattern&&!this.isComposing)?z(`div`,{class:`${s}-base-selection-placeholder ${s}-base-selection-overlay`},z(`div`,{class:`${s}-base-selection-placeholder__inner`},this.placeholder)):null,C=i?z(`div`,{ref:`patternInputWrapperRef`,class:`${s}-base-selection-tags`},y,f?null:l,g):z(`div`,{ref:`multipleElRef`,class:`${s}-base-selection-tags`,tabindex:r?void 0:0},y,g);_=z(F,null,h?z(ae,Object.assign({},x,{scrollable:!0,style:`max-height: calc(var(--v-target-height) * 6.6);`}),{trigger:()=>C,default:b}):C,S)}else if(i){let e=this.pattern||this.isComposing,t=this.active?!e:!this.selected,n=this.active?!1:this.selected;_=z(`div`,{ref:`patternInputWrapperRef`,class:`${s}-base-selection-label`,title:this.patternInputFocused?void 0:Ce(this.label)},z(`input`,Object.assign({},this.inputProps,{ref:`patternInputRef`,class:`${s}-base-selection-input`,value:this.active?this.pattern:``,placeholder:``,readonly:r,disabled:r,tabindex:-1,autofocus:this.autofocus,onFocus:this.handlePatternInputFocus,onBlur:this.handlePatternInputBlur,onInput:this.handlePatternInputInput,onCompositionstart:this.handleCompositionStart,onCompositionend:this.handleCompositionEnd})),n?z(`div`,{class:`${s}-base-selection-label__render-label ${s}-base-selection-overlay`,key:`input`},z(`div`,{class:`${s}-base-selection-overlay__wrapper`},u?u({option:this.selectedOption,handleClose:()=>{}}):d?d(this.selectedOption,!0):Te(this.label,this.selectedOption,!0))):null,t?z(`div`,{class:`${s}-base-selection-placeholder ${s}-base-selection-overlay`,key:`placeholder`},z(`div`,{class:`${s}-base-selection-overlay__wrapper`},this.filterablePlaceholder)):null,g)}else _=z(`div`,{ref:`singleElRef`,class:`${s}-base-selection-label`,tabindex:this.disabled?void 0:0},this.label===void 0?z(`div`,{class:`${s}-base-selection-placeholder ${s}-base-selection-overlay`,key:`placeholder`},z(`div`,{class:`${s}-base-selection-placeholder__inner`},this.placeholder)):z(`div`,{class:`${s}-base-selection-input`,title:Ce(this.label),key:`input`},z(`div`,{class:`${s}-base-selection-input__content`},u?u({option:this.selectedOption,handleClose:()=>{}}):d?d(this.selectedOption,!0):Te(this.label,this.selectedOption,!0))),g);return z(`div`,{ref:`selfRef`,class:[`${s}-base-selection`,this.rtlEnabled&&`${s}-base-selection--rtl`,this.themeClass,e&&`${s}-base-selection--${e}-status`,{[`${s}-base-selection--active`]:this.active,[`${s}-base-selection--selected`]:this.selected||this.active&&this.pattern,[`${s}-base-selection--disabled`]:this.disabled,[`${s}-base-selection--multiple`]:this.multiple,[`${s}-base-selection--focus`]:this.focused}],style:this.cssVars,onClick:this.onClick,onMouseenter:this.handleMouseEnter,onMouseleave:this.handleMouseLeave,onKeydown:this.onKeydown,onFocusin:this.handleFocusin,onFocusout:this.handleFocusout,onMousedown:this.handleMouseDown},_,o?z(`div`,{class:`${s}-base-selection__border`}):null,o?z(`div`,{class:`${s}-base-selection__state-border`}):null)}});function Ot(e){return e.type===`group`}function kt(e){return e.type===`ignored`}function At(e,t){try{return!!(1+t.toString().toLowerCase().indexOf(e.trim().toLowerCase()))}catch{return!1}}function jt(e,t){return{getIsGroup:Ot,getIgnored:kt,getKey(t){return Ot(t)?t.name||t.key||`key-required`:t[e]},getChildren(e){return e[t]}}}function Mt(e,t,n,r){if(!t)return e;function i(e){if(!Array.isArray(e))return[];let a=[];for(let o of e)if(Ot(o)){let e=i(o[r]);e.length&&a.push(Object.assign({},o,{[r]:e}))}else if(kt(o))continue;else t(n,o)&&a.push(o);return a}return i(e)}function Nt(e,t,n){let r=new Map;return e.forEach(e=>{Ot(e)?e[n].forEach(e=>{r.set(e[t],e)}):r.set(e[t],e)}),r}var Pt=H([Q(`select`,`
 z-index: auto;
 outline: none;
 width: 100%;
 position: relative;
 font-weight: var(--n-font-weight);
 `),Q(`select-menu`,`
 margin: 4px 0;
 box-shadow: var(--n-menu-box-shadow);
 `,[k({originalTransition:`background-color .3s var(--n-bezier), box-shadow .3s var(--n-bezier)`})])]),Ft=N({name:`Select`,props:Object.assign(Object.assign({},X.props),{to:c.propTo,bordered:{type:Boolean,default:void 0},clearable:Boolean,clearCreatedOptionsOnClear:{type:Boolean,default:!0},clearFilterAfterSelect:{type:Boolean,default:!0},options:{type:Array,default:()=>[]},defaultValue:{type:[String,Number,Array],default:null},keyboard:{type:Boolean,default:!0},value:[String,Number,Array],placeholder:String,menuProps:Object,multiple:Boolean,size:String,menuSize:{type:String},filterable:Boolean,disabled:{type:Boolean,default:void 0},remote:Boolean,loading:Boolean,filter:Function,placement:{type:String,default:`bottom-start`},widthMode:{type:String,default:`trigger`},tag:Boolean,onCreate:Function,fallbackOption:{type:[Function,Boolean],default:void 0},show:{type:Boolean,default:void 0},showArrow:{type:Boolean,default:!0},maxTagCount:[Number,String],ellipsisTagPopoverProps:Object,consistentMenuWidth:{type:Boolean,default:!0},virtualScroll:{type:Boolean,default:!0},labelField:{type:String,default:`label`},valueField:{type:String,default:`value`},childrenField:{type:String,default:`children`},renderLabel:Function,renderOption:Function,renderTag:Function,"onUpdate:value":[Function,Array],inputProps:Object,nodeProps:Function,ignoreComposition:{type:Boolean,default:!0},showOnFocus:Boolean,onUpdateValue:[Function,Array],onBlur:[Function,Array],onClear:[Function,Array],onFocus:[Function,Array],onScroll:[Function,Array],onSearch:[Function,Array],onUpdateShow:[Function,Array],"onUpdate:show":[Function,Array],displayDirective:{type:String,default:`show`},resetMenuOnOptionsChange:{type:Boolean,default:!0},status:String,showCheckmark:{type:Boolean,default:!0},scrollbarProps:Object,onChange:[Function,Array],items:Array}),slots:Object,setup(e){let{mergedClsPrefixRef:n,mergedBorderedRef:r,namespaceRef:i,inlineThemeDisabled:a,mergedComponentPropsRef:o}=ve(e),s=X(`Select`,`-select`,Pt,fe,e,n),l=Z(e.defaultValue),u=t(J(e,`value`),l),f=Z(!1),p=Z(``),m=ie(e,[`items`,`options`]),h=Z([]),g=Z([]),y=R(()=>g.value.concat(h.value).concat(m.value)),x=R(()=>{let{filter:t}=e;if(t)return t;let{labelField:n,valueField:r}=e;return(e,t)=>{if(!t)return!1;let i=t[n];if(typeof i==`string`)return At(e,i);let a=t[r];return typeof a==`string`?At(e,a):typeof a==`number`?At(e,String(a)):!1}}),S=R(()=>{if(e.remote)return m.value;{let{value:t}=y,{value:n}=p;return!n.length||!e.filterable?t:Mt(t,x.value,n,e.childrenField)}}),C=R(()=>{let{valueField:t,childrenField:n}=e,r=jt(t,n);return dt(S.value,r)}),w=R(()=>Nt(y.value,e.valueField,e.childrenField)),T=Z(!1),D=t(J(e,`show`),T),O=Z(null),ne=Z(null),k=Z(null),{localeRef:A}=te(`Select`),ae=R(()=>e.placeholder??A.value.placeholder),j=[],M=Z(new Map),N=R(()=>{let{fallbackOption:t}=e;if(t===void 0){let{labelField:t,valueField:n}=e;return e=>({[t]:String(e),[n]:e})}return t===!1?!1:e=>Object.assign(t(e),{value:e})});function P(t){let n=e.remote,{value:r}=M,{value:i}=w,{value:a}=N,o=[];return t.forEach(e=>{if(i.has(e))o.push(i.get(e));else if(n&&r.has(e))o.push(r.get(e));else if(a){let t=a(e);t&&o.push(t)}}),o}let F=R(()=>{if(e.multiple){let{value:e}=u;return Array.isArray(e)?P(e):[]}return null}),oe=R(()=>{let{value:t}=u;return!e.multiple&&!Array.isArray(t)?t===null?null:P([t])[0]||null:null}),I=v(e,{mergedSize:t=>{let{size:n}=e;if(n)return n;let{mergedSize:r}=t||{};return r?.value?r.value:o?.value?.Select?.size||`medium`}}),{mergedSizeRef:L,mergedDisabledRef:z,mergedStatusRef:se}=I;function B(t,n){let{onChange:r,"onUpdate:value":i,onUpdateValue:a}=e,{nTriggerFormChange:o,nTriggerFormInput:s}=I;r&&d(r,t,n),a&&d(a,t,n),i&&d(i,t,n),l.value=t,o(),s()}function V(t){let{onBlur:n}=e,{nTriggerFormBlur:r}=I;n&&d(n,t),r()}function ce(){let{onClear:t}=e;t&&d(t)}function H(t){let{onFocus:n,showOnFocus:r}=e,{nTriggerFormFocus:i}=I;n&&d(n,t),i(),r&&W()}function U(t){let{onSearch:n}=e;n&&d(n,t)}function le(t){let{onScroll:n}=e;n&&d(n,t)}function ue(){var t;let{remote:n,multiple:r}=e;if(n){let{value:n}=M;if(r){let{valueField:r}=e;(t=F.value)==null||t.forEach(e=>{n.set(e[r],e)})}else{let t=oe.value;t&&n.set(t[e.valueField],t)}}}function de(t){let{onUpdateShow:n,"onUpdate:show":r}=e;n&&d(n,t),r&&d(r,t),T.value=t}function W(){z.value||(de(!0),T.value=!0,e.filterable&&je())}function G(){de(!1)}function K(){p.value=``,g.value=j}let q=Z(!1);function pe(){e.filterable&&(q.value=!0)}function me(){e.filterable&&(q.value=!1,D.value||K())}function he(){z.value||(D.value?e.filterable?je():G():W())}function _e(e){(k.value?.selfRef)?.contains(e.relatedTarget)||(f.value=!1,V(e),G())}function Y(e){H(e),f.value=!0}function Q(){f.value=!0}function ye(e){O.value?.$el.contains(e.relatedTarget)||(f.value=!1,V(e),G())}function $(){var e;(e=O.value)==null||e.focus(),G()}function be(e){D.value&&(O.value?.$el.contains(b(e))||G())}function xe(t){if(!Array.isArray(t))return[];if(N.value)return Array.from(t);{let{remote:n}=e,{value:r}=w;if(n){let{value:e}=M;return t.filter(t=>r.has(t)||e.has(t))}else return t.filter(e=>r.has(e))}}function Se(e){Ce(e.rawNode)}function Ce(t){if(z.value)return;let{tag:n,remote:r,clearFilterAfterSelect:i,valueField:a}=e;if(n&&!r){let{value:e}=g,t=e[0]||null;if(t){let e=h.value;e.length?e.push(t):h.value=[t],g.value=j}}if(r&&M.value.set(t[a],t),e.multiple){let e=xe(u.value),o=e.findIndex(e=>e===t[a]);if(~o){if(e.splice(o,1),n&&!r){let e=we(t[a]);~e&&(h.value.splice(e,1),i&&(p.value=``))}}else e.push(t[a]),i&&(p.value=``);B(e,P(e))}else{if(n&&!r){let e=we(t[a]);~e?h.value=[h.value[e]]:h.value=j}Ae(),G(),B(t[a],t)}}function we(t){return h.value.findIndex(n=>n[e.valueField]===t)}function Te(t){D.value||W();let{value:n}=t.target;p.value=n;let{tag:r,remote:i}=e;if(U(n),r&&!i){if(!n){g.value=j;return}let{onCreate:t}=e,r=t?t(n):{[e.labelField]:n,[e.valueField]:n},{valueField:i,labelField:a}=e;m.value.some(e=>e[i]===r[i]||e[a]===r[a])||h.value.some(e=>e[i]===r[i]||e[a]===r[a])?g.value=j:g.value=[r]}}function Ee(t){t.stopPropagation();let{multiple:n,tag:r,remote:i,clearCreatedOptionsOnClear:a}=e;!n&&e.filterable&&G(),r&&!i&&a&&(h.value=j),ce(),n?B([],[]):B(null,null)}function De(e){!E(e,`action`)&&!E(e,`empty`)&&!E(e,`header`)&&e.preventDefault()}function Oe(e){le(e)}function ke(t){var n,r,i;if(!e.keyboard){t.preventDefault();return}switch(t.key){case` `:if(e.filterable)break;t.preventDefault();case`Enter`:if(!O.value?.isComposing){if(D.value){let t=k.value?.getPendingTmNode();t?Se(t):e.filterable||(G(),Ae())}else if(W(),e.tag&&q.value){let t=g.value[0];if(t){let n=t[e.valueField],{value:r}=u;e.multiple&&Array.isArray(r)&&r.includes(n)||Ce(t)}}}t.preventDefault();break;case`ArrowUp`:if(t.preventDefault(),e.loading)return;D.value&&((n=k.value)==null||n.prev());break;case`ArrowDown`:if(t.preventDefault(),e.loading)return;D.value?(r=k.value)==null||r.next():W();break;case`Escape`:D.value&&(re(t),G()),(i=O.value)==null||i.focus();break}}function Ae(){var e;(e=O.value)==null||e.focus()}function je(){var e;(e=O.value)==null||e.focusInput()}function Me(){var e;D.value&&((e=ne.value)==null||e.syncPosition())}ue(),ge(J(e,`options`),ue);let Ne={focus:()=>{var e;(e=O.value)==null||e.focus()},focusInput:()=>{var e;(e=O.value)==null||e.focusInput()},blur:()=>{var e;(e=O.value)==null||e.blur()},blurInput:()=>{var e;(e=O.value)==null||e.blurInput()}},Pe=R(()=>{let{self:{menuBoxShadow:e}}=s.value;return{"--n-menu-box-shadow":e}}),Fe=a?_(`select`,void 0,Pe,e):void 0;return Object.assign(Object.assign({},Ne),{mergedStatus:se,mergedClsPrefix:n,mergedBordered:r,namespace:i,treeMate:C,isMounted:ee(),triggerRef:O,menuRef:k,pattern:p,uncontrolledShow:T,mergedShow:D,adjustedTo:c(e),uncontrolledValue:l,mergedValue:u,followerRef:ne,localizedPlaceholder:ae,selectedOption:oe,selectedOptions:F,mergedSize:L,mergedDisabled:z,focused:f,activeWithoutMenuOpen:q,inlineThemeDisabled:a,onTriggerInputFocus:pe,onTriggerInputBlur:me,handleTriggerOrMenuResize:Me,handleMenuFocus:Q,handleMenuBlur:ye,handleMenuTabOut:$,handleTriggerClick:he,handleToggle:Se,handleDeleteOption:Ce,handlePatternInput:Te,handleClear:Ee,handleTriggerBlur:_e,handleTriggerFocus:Y,handleKeydown:ke,handleMenuAfterLeave:K,handleMenuClickOutside:be,handleMenuScroll:Oe,handleMenuKeydown:ke,handleMenuMousedown:De,mergedTheme:s,cssVars:a?void 0:Pe,themeClass:Fe?.themeClass,onRender:Fe?.onRender})},render(){return z(`div`,{class:`${this.mergedClsPrefix}-select`},z(s,null,{default:()=>[z(y,null,{default:()=>z(Dt,{ref:`triggerRef`,inlineThemeDisabled:this.inlineThemeDisabled,status:this.mergedStatus,inputProps:this.inputProps,clsPrefix:this.mergedClsPrefix,showArrow:this.showArrow,maxTagCount:this.maxTagCount,ellipsisTagPopoverProps:this.ellipsisTagPopoverProps,bordered:this.mergedBordered,active:this.activeWithoutMenuOpen||this.mergedShow,pattern:this.pattern,placeholder:this.localizedPlaceholder,selectedOption:this.selectedOption,selectedOptions:this.selectedOptions,multiple:this.multiple,renderTag:this.renderTag,renderLabel:this.renderLabel,filterable:this.filterable,clearable:this.clearable,disabled:this.mergedDisabled,size:this.mergedSize,theme:this.mergedTheme.peers.InternalSelection,labelField:this.labelField,valueField:this.valueField,themeOverrides:this.mergedTheme.peerOverrides.InternalSelection,loading:this.loading,focused:this.focused,onClick:this.handleTriggerClick,onDeleteOption:this.handleDeleteOption,onPatternInput:this.handlePatternInput,onClear:this.handleClear,onBlur:this.handleTriggerBlur,onFocus:this.handleTriggerFocus,onKeydown:this.handleKeydown,onPatternBlur:this.onTriggerInputBlur,onPatternFocus:this.onTriggerInputFocus,onResize:this.handleTriggerOrMenuResize,ignoreComposition:this.ignoreComposition},{arrow:()=>{var e;return[(e=this.$slots).arrow?.call(e)]}})}),z(i,{ref:`followerRef`,show:this.mergedShow,to:this.adjustedTo,teleportDisabled:this.adjustedTo===c.tdkey,containerClass:this.namespace,width:this.consistentMenuWidth?`target`:void 0,minWidth:`target`,placement:this.placement},{default:()=>z(oe,{name:`fade-in-scale-up-transition`,appear:this.isMounted,onAfterLeave:this.handleMenuAfterLeave},{default:()=>{var t;return this.mergedShow||this.displayDirective===`show`?((t=this.onRender)==null||t.call(this),de(z(vt,Object.assign({},this.menuProps,{ref:`menuRef`,onResize:this.handleTriggerOrMenuResize,inlineThemeDisabled:this.inlineThemeDisabled,virtualScroll:this.consistentMenuWidth&&this.virtualScroll,class:[`${this.mergedClsPrefix}-select-menu`,this.themeClass,this.menuProps?.class],clsPrefix:this.mergedClsPrefix,focusable:!0,labelField:this.labelField,valueField:this.valueField,autoPending:!0,nodeProps:this.nodeProps,theme:this.mergedTheme.peers.InternalSelectMenu,themeOverrides:this.mergedTheme.peerOverrides.InternalSelectMenu,treeMate:this.treeMate,multiple:this.multiple,size:this.menuSize,renderOption:this.renderOption,renderLabel:this.renderLabel,value:this.mergedValue,style:[this.menuProps?.style,this.cssVars],onToggle:this.handleToggle,onScroll:this.handleMenuScroll,onFocus:this.handleMenuFocus,onBlur:this.handleMenuBlur,onKeydown:this.handleMenuKeydown,onTabOut:this.handleMenuTabOut,onMousedown:this.handleMenuMousedown,show:this.mergedShow,showCheckmark:this.showCheckmark,resetMenuOnOptionsChange:this.resetMenuOnOptionsChange,scrollbarProps:this.scrollbarProps}),{empty:()=>{var e;return[(e=this.$slots).empty?.call(e)]},header:()=>{var e;return[(e=this.$slots).header?.call(e)]},action:()=>{var e;return[(e=this.$slots).action?.call(e)]}}),this.displayDirective===`show`?[[I,this.mergedShow],[e,this.handleMenuClickOutside,void 0,{capture:!0}]]:[[e,this.handleMenuClickOutside,void 0,{capture:!0}]])):null}})})]}))}});export{Ft as t};
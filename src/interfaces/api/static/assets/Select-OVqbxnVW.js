import{C as e,Et as t,Ft as n,Gn as r,Ht as i,Kt as a,Ln as o,Mn as s,O as c,Pn as l,Pt as u,Qn as d,Qt as f,Rt as p,Sn as m,St as h,Un as g,Xn as _,Yn as v,Yt as y,Zt as b,_ as x,_t as S,ar as C,bt as w,ct as T,en as E,ht as D,j as O,jn as k,kn as A,mn as j,nn as M,nr as N,ot as ee,pt as P,qt as F,rn as I,st as L,tn as R,un as z,ut as B,vn as V,wt as H,x as te,zn as U}from"./jobs-B39UCt_f.js";import{a as ne,c as W,d as re,i as G,l as K,o as q,r as J,s as ie,u as ae}from"./PageHeader-7euL3iK6.js";import{i as oe,n as se,o as ce,s as Y,t as X}from"./Suffix-DUgqrQJ7.js";import{a as le,r as Z}from"./GlossaryTip-DOYNcgSl.js";import{A as ue,D as de,E as fe,K as Q,S as pe,T as me,X as he,g as ge,w as _e,x as ve}from"./index-Br3yufnB.js";var $=`v-hidden`,ye=G(`[v-hidden]`,{display:`none!important`}),be=A({name:`Overflow`,props:{getCounter:Function,getTail:Function,updateCounter:Function,onUpdateCount:Function,onUpdateOverflow:Function},setup(e,{slots:t}){let n=N(null),r=N(null);function i(i){let{value:a}=n,{getCounter:o,getTail:s}=e,c;if(c=o===void 0?r.value:o(),!a||!c)return;c.hasAttribute($)&&c.removeAttribute($);let{children:l}=a;if(i.showAllItemsBeforeCalculate)for(let e of l)e.hasAttribute($)&&e.removeAttribute($);let u=a.offsetWidth,d=[],f=t.tail?s?.():null,p=f?f.offsetWidth:0,m=!1,h=a.children.length-+!!t.tail;for(let t=0;t<h-1;++t){if(t<0)continue;let n=l[t];if(m){n.hasAttribute($)||n.setAttribute($,``);continue}else n.hasAttribute($)&&n.removeAttribute($);let r=n.offsetWidth;if(p+=r,d[t]=r,p>u){let{updateCounter:n}=e;for(let r=t;r>=0;--r){let i=h-1-r;n===void 0?c.textContent=`${i}`:n(i);let a=c.offsetWidth;if(p-=d[r],p+a<=u||r===0){m=!0,t=r-1,f&&(t===-1?(f.style.maxWidth=`${u-a}px`,f.style.boxSizing=`border-box`):f.style.maxWidth=``);let{onUpdateCount:n}=e;n&&n(i);break}}}}let{onUpdateOverflow:g}=e;m?g!==void 0&&g(!0):(g!==void 0&&g(!1),c.setAttribute($,``))}let a=H();return ye.mount({id:`vueuc/overflow`,head:!0,anchorMetaName:ne,ssr:a}),U(()=>i({showAllItemsBeforeCalculate:!1})),{selfRef:n,counterRef:r,sync:i}},render(){let{$slots:e}=this;return l(()=>this.sync({showAllItemsBeforeCalculate:!1})),k(`div`,{class:`v-overflow`,ref:`selfRef`},[r(e,`default`),e.counter?e.counter():k(`span`,{style:{display:`inline-block`},ref:`counterRef`}),e.tail?e.tail():null])}});function xe(e,t){t&&(U(()=>{let{value:n}=e;n&&h.registerHandler(n,t)}),v(e,(e,t)=>{t&&h.unregisterHandler(t)},{deep:!1}),o(()=>{let{value:t}=e;t&&h.unregisterHandler(t)}))}function Se(e){switch(typeof e){case`string`:return e||void 0;case`number`:return String(e);default:return}}function Ce(e){let t=e.filter(e=>e!==void 0);if(t.length!==0)return t.length===1?t[0]:t=>{e.forEach(e=>{e&&e(t)})}}var we=A({name:`Checkmark`,render(){return k(`svg`,{xmlns:`http://www.w3.org/2000/svg`,viewBox:`0 0 16 16`},k(`g`,{fill:`none`},k(`path`,{d:`M14.046 3.486a.75.75 0 0 1-.032 1.06l-7.93 7.474a.85.85 0 0 1-1.188-.022l-2.68-2.72a.75.75 0 1 1 1.068-1.053l2.234 2.267l7.468-7.038a.75.75 0 0 1 1.06.032z`,fill:`currentColor`})))}}),Te=A({name:`Empty`,render(){return k(`svg`,{viewBox:`0 0 28 28`,fill:`none`,xmlns:`http://www.w3.org/2000/svg`},k(`path`,{d:`M26 7.5C26 11.0899 23.0899 14 19.5 14C15.9101 14 13 11.0899 13 7.5C13 3.91015 15.9101 1 19.5 1C23.0899 1 26 3.91015 26 7.5ZM16.8536 4.14645C16.6583 3.95118 16.3417 3.95118 16.1464 4.14645C15.9512 4.34171 15.9512 4.65829 16.1464 4.85355L18.7929 7.5L16.1464 10.1464C15.9512 10.3417 15.9512 10.6583 16.1464 10.8536C16.3417 11.0488 16.6583 11.0488 16.8536 10.8536L19.5 8.20711L22.1464 10.8536C22.3417 11.0488 22.6583 11.0488 22.8536 10.8536C23.0488 10.6583 23.0488 10.3417 22.8536 10.1464L20.2071 7.5L22.8536 4.85355C23.0488 4.65829 23.0488 4.34171 22.8536 4.14645C22.6583 3.95118 22.3417 3.95118 22.1464 4.14645L19.5 6.79289L16.8536 4.14645Z`,fill:`currentColor`}),k(`path`,{d:`M25 22.75V12.5991C24.5572 13.0765 24.053 13.4961 23.5 13.8454V16H17.5L17.3982 16.0068C17.0322 16.0565 16.75 16.3703 16.75 16.75C16.75 18.2688 15.5188 19.5 14 19.5C12.4812 19.5 11.25 18.2688 11.25 16.75L11.2432 16.6482C11.1935 16.2822 10.8797 16 10.5 16H4.5V7.25C4.5 6.2835 5.2835 5.5 6.25 5.5H12.2696C12.4146 4.97463 12.6153 4.47237 12.865 4H6.25C4.45507 4 3 5.45507 3 7.25V22.75C3 24.5449 4.45507 26 6.25 26H21.75C23.5449 26 25 24.5449 25 22.75ZM4.5 22.75V17.5H9.81597L9.85751 17.7041C10.2905 19.5919 11.9808 21 14 21L14.215 20.9947C16.2095 20.8953 17.842 19.4209 18.184 17.5H23.5V22.75C23.5 23.7165 22.7165 24.5 21.75 24.5H6.25C5.2835 24.5 4.5 23.7165 4.5 22.75Z`,fill:`currentColor`}))}});function Ee(e){return Array.isArray(e)?e:[e]}var De={STOP:`STOP`};function Oe(e,t){let n=t(e);e.children!==void 0&&n!==De.STOP&&e.children.forEach(e=>Oe(e,t))}function ke(e,t={}){let{preserveGroup:n=!1}=t,r=[],i=n?e=>{e.isLeaf||(r.push(e.key),a(e.children))}:e=>{e.isLeaf||(e.isGroup||r.push(e.key),a(e.children))};function a(e){e.forEach(i)}return a(e),r}function Ae(e,t){let{isLeaf:n}=e;return n===void 0?!t(e):n}function je(e){return e.children}function Me(e){return e.key}function Ne(){return!1}function Pe(e,t){let{isLeaf:n}=e;return!(n===!1&&!Array.isArray(t(e)))}function Fe(e){return e.disabled===!0}function Ie(e,t){return e.isLeaf===!1&&!Array.isArray(t(e))}function Le(e){return e==null?[]:Array.isArray(e)?e:e.checkedKeys??[]}function Re(e){return e==null||Array.isArray(e)?[]:e.indeterminateKeys??[]}function ze(e,t){let n=new Set(e);return t.forEach(e=>{n.has(e)||n.add(e)}),Array.from(n)}function Be(e,t){let n=new Set(e);return t.forEach(e=>{n.has(e)&&n.delete(e)}),Array.from(n)}function Ve(e){return e?.type===`group`}function He(e){let t=new Map;return e.forEach((e,n)=>{t.set(e.key,n)}),e=>t.get(e)??null}var Ue=class extends Error{constructor(){super(),this.message=`SubtreeNotLoadedError: checking a subtree whose required nodes are not fully loaded.`}};function We(e,t,n,r){return Je(t.concat(e),n,r,!1)}function Ge(e,t){let n=new Set;return e.forEach(e=>{let r=t.treeNodeMap.get(e);if(r!==void 0){let e=r.parent;for(;e!==null&&!(e.disabled||n.has(e.key));)n.add(e.key),e=e.parent}}),n}function Ke(e,t,n,r){let i=Je(t,n,r,!1),a=Je(e,n,r,!0),o=Ge(e,n),s=[];return i.forEach(e=>{(a.has(e)||o.has(e))&&s.push(e)}),s.forEach(e=>i.delete(e)),i}function qe(e,t){let{checkedKeys:n,keysToCheck:r,keysToUncheck:i,indeterminateKeys:a,cascade:o,leafOnly:s,checkStrategy:c,allowNotLoaded:l}=e;if(!o)return r===void 0?i===void 0?{checkedKeys:Array.from(n),indeterminateKeys:Array.from(a)}:{checkedKeys:Be(n,i),indeterminateKeys:Array.from(a)}:{checkedKeys:ze(n,r),indeterminateKeys:Array.from(a)};let{levelTreeNodeMap:u}=t,d;d=i===void 0?r===void 0?Je(n,t,l,!1):We(r,n,t,l):Ke(i,n,t,l);let f=c===`parent`,p=c===`child`||s,m=d,h=new Set,g=Math.max.apply(null,Array.from(u.keys()));for(let e=g;e>=0;--e){let t=e===0,n=u.get(e);for(let e of n){if(e.isLeaf)continue;let{key:n,shallowLoaded:r}=e;if(p&&r&&e.children.forEach(e=>{!e.disabled&&!e.isLeaf&&e.shallowLoaded&&m.has(e.key)&&m.delete(e.key)}),e.disabled||!r)continue;let i=!0,a=!1,o=!0;for(let t of e.children){let e=t.key;if(!t.disabled){if(o&&=!1,m.has(e))a=!0;else if(h.has(e)){a=!0,i=!1;break}else if(i=!1,a)break}}i&&!o?(f&&e.children.forEach(e=>{!e.disabled&&m.has(e.key)&&m.delete(e.key)}),m.add(n)):a&&h.add(n),t&&p&&m.has(n)&&m.delete(n)}}return{checkedKeys:Array.from(m),indeterminateKeys:Array.from(h)}}function Je(e,t,n,r){let{treeNodeMap:i,getChildren:a}=t,o=new Set,s=new Set(e);return e.forEach(e=>{let t=i.get(e);t!==void 0&&Oe(t,e=>{if(e.disabled)return De.STOP;let{key:t}=e;if(!o.has(t)&&(o.add(t),s.add(t),Ie(e.rawNode,a))){if(r)return De.STOP;if(!n)throw new Ue}})}),s}function Ye(e,{includeGroup:t=!1,includeSelf:n=!0},r){let i=r.treeNodeMap,a=e==null?null:i.get(e)??null,o={keyPath:[],treeNodePath:[],treeNode:a};if(a?.ignored)return o.treeNode=null,o;for(;a;)!a.ignored&&(t||!a.isGroup)&&o.treeNodePath.push(a),a=a.parent;return o.treeNodePath.reverse(),n||o.treeNodePath.pop(),o.keyPath=o.treeNodePath.map(e=>e.key),o}function Xe(e){if(e.length===0)return null;let t=e[0];return t.isGroup||t.ignored||t.disabled?t.getNext():t}function Ze(e,t){let n=e.siblings,r=n.length,{index:i}=e;return t?n[(i+1)%r]:i===n.length-1?null:n[i+1]}function Qe(e,t,{loop:n=!1,includeDisabled:r=!1}={}){let i=t===`prev`?$e:Ze,a={reverse:t===`prev`},o=!1,s=null;function c(t){if(t!==null){if(t===e){if(!o)o=!0;else if(!e.disabled&&!e.isGroup){s=e;return}}else if((!t.disabled||r)&&!t.ignored&&!t.isGroup){s=t;return}if(t.isGroup){let e=tt(t,a);e===null?c(i(t,n)):s=e}else{let e=i(t,!1);if(e!==null)c(e);else{let e=et(t);e?.isGroup?c(i(e,n)):n&&c(i(t,!0))}}}}return c(e),s}function $e(e,t){let n=e.siblings,r=n.length,{index:i}=e;return t?n[(i-1+r)%r]:i===0?null:n[i-1]}function et(e){return e.parent}function tt(e,t={}){let{reverse:n=!1}=t,{children:r}=e;if(r){let{length:e}=r,i=n?e-1:0,a=n?-1:e,o=n?-1:1;for(let e=i;e!==a;e+=o){let n=r[e];if(!n.disabled&&!n.ignored)if(n.isGroup){let e=tt(n,t);if(e!==null)return e}else return n}}return null}var nt={getChild(){return this.ignored?null:tt(this)},getParent(){let{parent:e}=this;return e?.isGroup?e.getParent():e},getNext(e={}){return Qe(this,`next`,e)},getPrev(e={}){return Qe(this,`prev`,e)}};function rt(e,t){let n=t?new Set(t):void 0,r=[];function i(e){e.forEach(e=>{r.push(e),!(e.isLeaf||!e.children||e.ignored)&&(e.isGroup||n===void 0||n.has(e.key))&&i(e.children)})}return i(e),r}function it(e,t){let n=e.key;for(;t;){if(t.key===n)return!0;t=t.parent}return!1}function at(e,t,n,r,i,a=null,o=0){let s=[];return e.forEach((c,l)=>{var u;let d=Object.create(r);if(d.rawNode=c,d.siblings=s,d.level=o,d.index=l,d.isFirstChild=l===0,d.isLastChild=l+1===e.length,d.parent=a,!d.ignored){let e=i(c);Array.isArray(e)&&(d.children=at(e,t,n,r,i,d,o+1))}s.push(d),t.set(d.key,d),n.has(o)||n.set(o,[]),(u=n.get(o))==null||u.push(d)}),s}function ot(e,t={}){let n=new Map,r=new Map,{getDisabled:i=Fe,getIgnored:a=Ne,getIsGroup:o=Ve,getKey:s=Me}=t,c=t.getChildren??je,l=t.ignoreEmptyChildren?e=>{let t=c(e);return Array.isArray(t)?t.length?t:null:t}:c,u=at(e,n,r,Object.assign({get key(){return s(this.rawNode)},get disabled(){return i(this.rawNode)},get isGroup(){return o(this.rawNode)},get isLeaf(){return Ae(this.rawNode,l)},get shallowLoaded(){return Pe(this.rawNode,l)},get ignored(){return a(this.rawNode)},contains(e){return it(this,e)}},nt),l);function d(e){if(e==null)return null;let t=n.get(e);return t&&!t.isGroup&&!t.ignored?t:null}function f(e){if(e==null)return null;let t=n.get(e);return t&&!t.ignored?t:null}function p(e,t){let n=f(e);return n?n.getPrev(t):null}function m(e,t){let n=f(e);return n?n.getNext(t):null}function h(e){let t=f(e);return t?t.getParent():null}function g(e){let t=f(e);return t?t.getChild():null}let _={treeNodes:u,treeNodeMap:n,levelTreeNodeMap:r,maxLevel:Math.max(...r.keys()),getChildren:l,getFlattenedNodes(e){return rt(u,e)},getNode:d,getPrev:p,getNext:m,getParent:h,getChild:g,getFirstAvailableNode(){return Xe(u)},getPath(e,t={}){return Ye(e,t,_)},getCheckedKeys(e,t={}){let{cascade:n=!0,leafOnly:r=!1,checkStrategy:i=`all`,allowNotLoaded:a=!1}=t;return qe({checkedKeys:Le(e),indeterminateKeys:Re(e),cascade:n,leafOnly:r,checkStrategy:i,allowNotLoaded:a},_)},check(e,t,n={}){let{cascade:r=!0,leafOnly:i=!1,checkStrategy:a=`all`,allowNotLoaded:o=!1}=n;return qe({checkedKeys:Le(t),indeterminateKeys:Re(t),keysToCheck:e==null?[]:Ee(e),cascade:r,leafOnly:i,checkStrategy:a,allowNotLoaded:o},_)},uncheck(e,t,n={}){let{cascade:r=!0,leafOnly:i=!1,checkStrategy:a=`all`,allowNotLoaded:o=!1}=n;return qe({checkedKeys:Le(t),indeterminateKeys:Re(t),keysToUncheck:e==null?[]:Ee(e),cascade:r,leafOnly:i,checkStrategy:a,allowNotLoaded:o},_)},getNonLeafKeys(e={}){return ke(u,e)}};return _}var st=f(`empty`,`
 display: flex;
 flex-direction: column;
 align-items: center;
 font-size: var(--n-font-size);
`,[E(`icon`,`
 width: var(--n-icon-size);
 height: var(--n-icon-size);
 font-size: var(--n-icon-size);
 line-height: var(--n-icon-size);
 color: var(--n-icon-color);
 transition:
 color .3s var(--n-bezier);
 `,[b(`+`,[E(`description`,`
 margin-top: 8px;
 `)])]),E(`description`,`
 transition: color .3s var(--n-bezier);
 color: var(--n-text-color);
 `),E(`extra`,`
 text-align: center;
 transition: color .3s var(--n-bezier);
 margin-top: 12px;
 color: var(--n-extra-text-color);
 `)]),ct=A({name:`Empty`,props:Object.assign(Object.assign({},c.props),{description:String,showDescription:{type:Boolean,default:!0},showIcon:{type:Boolean,default:!0},size:{type:String,default:`medium`},renderIcon:Function}),slots:Object,setup(e){let{mergedClsPrefixRef:t,inlineThemeDisabled:n,mergedComponentPropsRef:r}=T(e),i=c(`Empty`,`-empty`,st,fe,e,t),{localeRef:a}=oe(`Empty`),o=m(()=>e.description??r?.value?.Empty?.description),s=m(()=>r?.value?.Empty?.renderIcon||(()=>k(Te,null))),l=m(()=>{let{size:t}=e,{common:{cubicBezierEaseInOut:n},self:{[I(`iconSize`,t)]:r,[I(`fontSize`,t)]:a,textColor:o,iconColor:s,extraTextColor:c}}=i.value;return{"--n-icon-size":r,"--n-font-size":a,"--n-bezier":n,"--n-text-color":o,"--n-icon-color":s,"--n-extra-text-color":c}}),u=n?L(`empty`,m(()=>{let t=``,{size:n}=e;return t+=n[0],t}),l,e):void 0;return{mergedClsPrefix:t,mergedRenderIcon:s,localizedDescription:m(()=>o.value||a.value.description),cssVars:n?void 0:l,themeClass:u?.themeClass,onRender:u?.onRender}},render(){let{$slots:e,mergedClsPrefix:t,onRender:n}=this;return n?.(),k(`div`,{class:[`${t}-empty`,this.themeClass],style:this.cssVars},this.showIcon?k(`div`,{class:`${t}-empty__icon`},e.icon?e.icon():k(ue,{clsPrefix:t},{default:this.mergedRenderIcon})):null,this.showDescription?k(`div`,{class:`${t}-empty__description`},e.default?e.default():this.localizedDescription):null,e.extra?k(`div`,{class:`${t}-empty__extra`},e.extra()):null)}}),lt=A({name:`NBaseSelectGroupHeader`,props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(){let{renderLabelRef:e,renderOptionRef:t,labelFieldRef:n,nodePropsRef:r}=s(ae);return{labelField:n,nodeProps:r,renderLabel:e,renderOption:t}},render(){let{clsPrefix:e,renderLabel:t,renderOption:n,nodeProps:r,tmNode:{rawNode:i}}=this,a=r?.(i),o=t?t(i,!1):Q(i[this.labelField],i,!1),s=k(`div`,Object.assign({},a,{class:[`${e}-base-select-group-header`,a?.class]}),o);return i.render?i.render({node:s,option:i}):n?n({node:s,option:i,selected:!1}):s}});function ut(e,t){return k(z,{name:`fade-in-scale-up-transition`},{default:()=>e?k(ue,{clsPrefix:t,class:`${t}-base-select-option__check`},{default:()=>k(we)}):null})}var dt=A({name:`NBaseSelectOption`,props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(e){let{valueRef:t,pendingTmNodeRef:n,multipleRef:r,valueSetRef:i,renderLabelRef:a,renderOptionRef:o,labelFieldRef:c,valueFieldRef:l,showCheckmarkRef:u,nodePropsRef:d,handleOptionClick:f,handleOptionMouseEnter:m}=s(ae),h=p(()=>{let{value:t}=n;return t?e.tmNode.key===t.key:!1});function g(t){let{tmNode:n}=e;n.disabled||f(t,n)}function _(t){let{tmNode:n}=e;n.disabled||m(t,n)}function v(t){let{tmNode:n}=e,{value:r}=h;n.disabled||r||m(t,n)}return{multiple:r,isGrouped:p(()=>{let{tmNode:t}=e,{parent:n}=t;return n&&n.rawNode.type===`group`}),showCheckmark:u,nodeProps:d,isPending:h,isSelected:p(()=>{let{value:n}=t,{value:a}=r;if(n===null)return!1;let o=e.tmNode.rawNode[l.value];if(a){let{value:e}=i;return e.has(o)}else return n===o}),labelField:c,renderLabel:a,renderOption:o,handleMouseMove:v,handleMouseEnter:_,handleClick:g}},render(){let{clsPrefix:e,tmNode:{rawNode:t},isSelected:n,isPending:r,isGrouped:i,showCheckmark:a,nodeProps:o,renderOption:s,renderLabel:c,handleClick:l,handleMouseEnter:u,handleMouseMove:d}=this,f=ut(n,e),p=c?[c(t,n),a&&f]:[Q(t[this.labelField],t,n),a&&f],m=o?.(t),h=k(`div`,Object.assign({},m,{class:[`${e}-base-select-option`,t.class,m?.class,{[`${e}-base-select-option--disabled`]:t.disabled,[`${e}-base-select-option--selected`]:n,[`${e}-base-select-option--grouped`]:i,[`${e}-base-select-option--pending`]:r,[`${e}-base-select-option--show-checkmark`]:a}],style:[m?.style||``,t.style||``],onClick:Ce([l,m?.onClick]),onMouseenter:Ce([u,m?.onMouseenter]),onMousemove:Ce([d,m?.onMousemove])}),k(`div`,{class:`${e}-base-select-option__content`},p));return t.render?t.render({node:h,option:t,selected:n}):s?s({node:h,option:t,selected:n}):h}}),ft=f(`base-select-menu`,`
 line-height: 1.5;
 outline: none;
 z-index: 0;
 position: relative;
 border-radius: var(--n-border-radius);
 transition:
 background-color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier);
 background-color: var(--n-color);
`,[f(`scrollbar`,`
 max-height: var(--n-height);
 `),f(`virtual-list`,`
 max-height: var(--n-height);
 `),f(`base-select-option`,`
 min-height: var(--n-option-height);
 font-size: var(--n-option-font-size);
 display: flex;
 align-items: center;
 `,[E(`content`,`
 z-index: 1;
 white-space: nowrap;
 text-overflow: ellipsis;
 overflow: hidden;
 `)]),f(`base-select-group-header`,`
 min-height: var(--n-option-height);
 font-size: .93em;
 display: flex;
 align-items: center;
 `),f(`base-select-menu-option-wrapper`,`
 position: relative;
 width: 100%;
 `),E(`loading, empty`,`
 display: flex;
 padding: 12px 32px;
 flex: 1;
 justify-content: center;
 `),E(`loading`,`
 color: var(--n-loading-color);
 font-size: var(--n-loading-size);
 `),E(`header`,`
 padding: 8px var(--n-option-padding-left);
 font-size: var(--n-option-font-size);
 transition: 
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 border-bottom: 1px solid var(--n-action-divider-color);
 color: var(--n-action-text-color);
 `),E(`action`,`
 padding: 8px var(--n-option-padding-left);
 font-size: var(--n-option-font-size);
 transition: 
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 border-top: 1px solid var(--n-action-divider-color);
 color: var(--n-action-text-color);
 `),f(`base-select-group-header`,`
 position: relative;
 cursor: default;
 padding: var(--n-option-padding);
 color: var(--n-group-header-text-color);
 `),f(`base-select-option`,`
 cursor: pointer;
 position: relative;
 padding: var(--n-option-padding);
 transition:
 color .3s var(--n-bezier),
 opacity .3s var(--n-bezier);
 box-sizing: border-box;
 color: var(--n-option-text-color);
 opacity: 1;
 `,[R(`show-checkmark`,`
 padding-right: calc(var(--n-option-padding-right) + 20px);
 `),b(`&::before`,`
 content: "";
 position: absolute;
 left: 4px;
 right: 4px;
 top: 0;
 bottom: 0;
 border-radius: var(--n-border-radius);
 transition: background-color .3s var(--n-bezier);
 `),b(`&:active`,`
 color: var(--n-option-text-color-pressed);
 `),R(`grouped`,`
 padding-left: calc(var(--n-option-padding-left) * 1.5);
 `),R(`pending`,[b(`&::before`,`
 background-color: var(--n-option-color-pending);
 `)]),R(`selected`,`
 color: var(--n-option-text-color-active);
 `,[b(`&::before`,`
 background-color: var(--n-option-color-active);
 `),R(`pending`,[b(`&::before`,`
 background-color: var(--n-option-color-active-pending);
 `)])]),R(`disabled`,`
 cursor: not-allowed;
 `,[M(`selected`,`
 color: var(--n-option-text-color-disabled);
 `),R(`selected`,`
 opacity: var(--n-option-opacity-disabled);
 `)]),E(`check`,`
 font-size: 16px;
 position: absolute;
 right: calc(var(--n-option-padding-right) - 4px);
 top: calc(50% - 7px);
 color: var(--n-option-check-color);
 transition: color .3s var(--n-bezier);
 `,[_e({enterScale:`0.5`})])])]),pt=A({name:`InternalSelectMenu`,props:Object.assign(Object.assign({},c.props),{clsPrefix:{type:String,required:!0},scrollable:{type:Boolean,default:!0},treeMate:{type:Object,required:!0},multiple:Boolean,size:{type:String,default:`medium`},value:{type:[String,Number,Array],default:null},autoPending:Boolean,virtualScroll:{type:Boolean,default:!0},show:{type:Boolean,default:!0},labelField:{type:String,default:`label`},valueField:{type:String,default:`value`},loading:Boolean,focusable:Boolean,renderLabel:Function,renderOption:Function,nodeProps:Function,showCheckmark:{type:Boolean,default:!0},onMousedown:Function,onScroll:Function,onFocus:Function,onBlur:Function,onKeyup:Function,onKeydown:Function,onTabOut:Function,onMouseenter:Function,onMouseleave:Function,onResize:Function,resetMenuOnOptionsChange:{type:Boolean,default:!0},inlineThemeDisabled:Boolean,scrollbarProps:Object,onToggle:Function}),setup(e){let{mergedClsPrefixRef:t,mergedRtlRef:n,mergedComponentPropsRef:r}=T(e),i=O(`InternalSelectMenu`,n,t),s=c(`InternalSelectMenu`,`-internal-select-menu`,ft,me,e,C(e,`clsPrefix`)),u=N(null),d=N(null),f=N(null),p=m(()=>e.treeMate.getFlattenedNodes()),h=m(()=>He(p.value)),_=N(null);function y(){let{treeMate:t}=e,n=null,{value:r}=e;r===null?n=t.getFirstAvailableNode():(n=e.multiple?t.getNode((r||[])[(r||[]).length-1]):t.getNode(r),(!n||n.disabled)&&(n=t.getFirstAvailableNode())),W(n||null)}function b(){let{value:t}=_;t&&!e.treeMate.getNode(t.key)&&(_.value=null)}let x;v(()=>e.show,t=>{t?x=v(()=>e.treeMate,()=>{e.resetMenuOnOptionsChange?(e.autoPending?y():b(),l(re)):b()},{immediate:!0}):x?.()},{immediate:!0}),o(()=>{x?.()});let S=m(()=>a(s.value.self[I(`optionHeight`,e.size)])),w=m(()=>F(s.value.self[I(`padding`,e.size)])),E=m(()=>e.multiple&&Array.isArray(e.value)?new Set(e.value):new Set),D=m(()=>{let e=p.value;return e&&e.length===0}),k=m(()=>r?.value?.Select?.renderEmpty);function A(t){let{onToggle:n}=e;n&&n(t)}function j(t){let{onScroll:n}=e;n&&n(t)}function M(e){var t;(t=f.value)==null||t.sync(),j(e)}function ee(){var e;(e=f.value)==null||e.sync()}function P(){let{value:e}=_;return e||null}function R(e,t){t.disabled||W(t,!1)}function z(e,t){t.disabled||A(t)}function B(t){var n;Y(t,`action`)||(n=e.onKeyup)==null||n.call(e,t)}function V(t){var n;Y(t,`action`)||(n=e.onKeydown)==null||n.call(e,t)}function H(t){var n;(n=e.onMousedown)==null||n.call(e,t),!e.focusable&&t.preventDefault()}function te(){let{value:e}=_;e&&W(e.getNext({loop:!0}),!0)}function ne(){let{value:e}=_;e&&W(e.getPrev({loop:!0}),!0)}function W(e,t=!1){_.value=e,t&&re()}function re(){var t,n;let r=_.value;if(!r)return;let i=h.value(r.key);i!==null&&(e.virtualScroll?(t=d.value)==null||t.scrollTo({index:i}):(n=f.value)==null||n.scrollTo({index:i,elSize:S.value}))}function G(t){var n;u.value?.contains(t.target)&&((n=e.onFocus)==null||n.call(e,t))}function q(t){var n;u.value?.contains(t.relatedTarget)||(n=e.onBlur)==null||n.call(e,t)}g(ae,{handleOptionMouseEnter:R,handleOptionClick:z,valueSetRef:E,pendingTmNodeRef:_,nodePropsRef:C(e,`nodeProps`),showCheckmarkRef:C(e,`showCheckmark`),multipleRef:C(e,`multiple`),valueRef:C(e,`value`),renderLabelRef:C(e,`renderLabel`),renderOptionRef:C(e,`renderOption`),labelFieldRef:C(e,`labelField`),valueFieldRef:C(e,`valueField`)}),g(K,u),U(()=>{let{value:e}=f;e&&e.sync()});let J=m(()=>{let{size:t}=e,{common:{cubicBezierEaseInOut:n},self:{height:r,borderRadius:i,color:a,groupHeaderTextColor:o,actionDividerColor:c,optionTextColorPressed:l,optionTextColor:u,optionTextColorDisabled:d,optionTextColorActive:f,optionOpacityDisabled:p,optionCheckColor:m,actionTextColor:h,optionColorPending:g,optionColorActive:_,loadingColor:v,loadingSize:y,optionColorActivePending:b,[I(`optionFontSize`,t)]:x,[I(`optionHeight`,t)]:S,[I(`optionPadding`,t)]:C}}=s.value;return{"--n-height":r,"--n-action-divider-color":c,"--n-action-text-color":h,"--n-bezier":n,"--n-border-radius":i,"--n-color":a,"--n-option-font-size":x,"--n-group-header-text-color":o,"--n-option-check-color":m,"--n-option-color-pending":g,"--n-option-color-active":_,"--n-option-color-active-pending":b,"--n-option-height":S,"--n-option-opacity-disabled":p,"--n-option-text-color":u,"--n-option-text-color-active":f,"--n-option-text-color-disabled":d,"--n-option-text-color-pressed":l,"--n-option-padding":C,"--n-option-padding-left":F(C,`left`),"--n-option-padding-right":F(C,`right`),"--n-loading-color":v,"--n-loading-size":y}}),{inlineThemeDisabled:ie}=e,oe=ie?L(`internal-select-menu`,m(()=>e.size[0]),J,e):void 0,se={selfRef:u,next:te,prev:ne,getPendingTmNode:P};return xe(u,e.onResize),Object.assign({mergedTheme:s,mergedClsPrefix:t,rtlEnabled:i,virtualListRef:d,scrollbarRef:f,itemSize:S,padding:w,flattenedNodes:p,empty:D,mergedRenderEmpty:k,virtualListContainer(){let{value:e}=d;return e?.listElRef},virtualListContent(){let{value:e}=d;return e?.itemsElRef},doScroll:j,handleFocusin:G,handleFocusout:q,handleKeyUp:B,handleKeyDown:V,handleMouseDown:H,handleVirtualListResize:ee,handleVirtualListScroll:M,cssVars:ie?void 0:J,themeClass:oe?.themeClass,onRender:oe?.onRender},se)},render(){let{$slots:t,virtualScroll:n,clsPrefix:r,mergedTheme:i,themeClass:a,onRender:o}=this;return o?.(),k(`div`,{ref:`selfRef`,tabindex:this.focusable?0:-1,class:[`${r}-base-select-menu`,`${r}-base-select-menu--${this.size}-size`,this.rtlEnabled&&`${r}-base-select-menu--rtl`,a,this.multiple&&`${r}-base-select-menu--multiple`],style:this.cssVars,onFocusin:this.handleFocusin,onFocusout:this.handleFocusout,onKeyup:this.handleKeyUp,onKeydown:this.handleKeyDown,onMousedown:this.handleMouseDown,onMouseenter:this.onMouseenter,onMouseleave:this.onMouseleave},D(t.header,e=>e&&k(`div`,{class:`${r}-base-select-menu__header`,"data-header":!0,key:`header`},e)),this.loading?k(`div`,{class:`${r}-base-select-menu__loading`},k(e,{clsPrefix:r,strokeWidth:20})):this.empty?k(`div`,{class:`${r}-base-select-menu__empty`,"data-empty":!0},P(t.empty,()=>[this.mergedRenderEmpty?.call(this)||k(ct,{theme:i.peers.Empty,themeOverrides:i.peerOverrides.Empty,size:this.size})])):k(x,Object.assign({ref:`scrollbarRef`,theme:i.peers.Scrollbar,themeOverrides:i.peerOverrides.Scrollbar,scrollable:this.scrollable,container:n?this.virtualListContainer:void 0,content:n?this.virtualListContent:void 0,onScroll:n?void 0:this.doScroll},this.scrollbarProps),{default:()=>n?k(ce,{ref:`virtualListRef`,class:`${r}-virtual-list`,items:this.flattenedNodes,itemSize:this.itemSize,showScrollbar:!1,paddingTop:this.padding.top,paddingBottom:this.padding.bottom,onResize:this.handleVirtualListResize,onScroll:this.handleVirtualListScroll,itemResizable:!0},{default:({item:e})=>e.isGroup?k(lt,{key:e.key,clsPrefix:r,tmNode:e}):e.ignored?null:k(dt,{clsPrefix:r,key:e.key,tmNode:e})}):k(`div`,{class:`${r}-base-select-menu-option-wrapper`,style:{paddingTop:this.padding.top,paddingBottom:this.padding.bottom}},this.flattenedNodes.map(e=>e.isGroup?k(lt,{key:e.key,clsPrefix:r,tmNode:e}):k(dt,{clsPrefix:r,key:e.key,tmNode:e})))}),D(t.action,e=>e&&[k(`div`,{class:`${r}-base-select-menu__action`,"data-action":!0,key:`action`},e),k(se,{onFocus:this.onTabOut,key:`focus-detector`})]))}});function mt(e){let{textColor2:t,primaryColorHover:n,primaryColorPressed:r,primaryColor:a,infoColor:o,successColor:s,warningColor:c,errorColor:l,baseColor:u,borderColor:d,opacityDisabled:f,tagColor:p,closeIconColor:m,closeIconColorHover:h,closeIconColorPressed:g,borderRadiusSmall:_,fontSizeMini:v,fontSizeTiny:y,fontSizeSmall:b,fontSizeMedium:x,heightMini:S,heightTiny:C,heightSmall:w,heightMedium:T,closeColorHover:E,closeColorPressed:D,buttonColor2Hover:O,buttonColor2Pressed:k,fontWeightStrong:A}=e;return Object.assign(Object.assign({},pe),{closeBorderRadius:_,heightTiny:S,heightSmall:C,heightMedium:w,heightLarge:T,borderRadius:_,opacityDisabled:f,fontSizeTiny:v,fontSizeSmall:y,fontSizeMedium:b,fontSizeLarge:x,fontWeightStrong:A,textColorCheckable:t,textColorHoverCheckable:t,textColorPressedCheckable:t,textColorChecked:u,colorCheckable:`#0000`,colorHoverCheckable:O,colorPressedCheckable:k,colorChecked:a,colorCheckedHover:n,colorCheckedPressed:r,border:`1px solid ${d}`,textColor:t,color:p,colorBordered:`rgb(250, 250, 252)`,closeIconColor:m,closeIconColorHover:h,closeIconColorPressed:g,closeColorHover:E,closeColorPressed:D,borderPrimary:`1px solid ${i(a,{alpha:.3})}`,textColorPrimary:a,colorPrimary:i(a,{alpha:.12}),colorBorderedPrimary:i(a,{alpha:.1}),closeIconColorPrimary:a,closeIconColorHoverPrimary:a,closeIconColorPressedPrimary:a,closeColorHoverPrimary:i(a,{alpha:.12}),closeColorPressedPrimary:i(a,{alpha:.18}),borderInfo:`1px solid ${i(o,{alpha:.3})}`,textColorInfo:o,colorInfo:i(o,{alpha:.12}),colorBorderedInfo:i(o,{alpha:.1}),closeIconColorInfo:o,closeIconColorHoverInfo:o,closeIconColorPressedInfo:o,closeColorHoverInfo:i(o,{alpha:.12}),closeColorPressedInfo:i(o,{alpha:.18}),borderSuccess:`1px solid ${i(s,{alpha:.3})}`,textColorSuccess:s,colorSuccess:i(s,{alpha:.12}),colorBorderedSuccess:i(s,{alpha:.1}),closeIconColorSuccess:s,closeIconColorHoverSuccess:s,closeIconColorPressedSuccess:s,closeColorHoverSuccess:i(s,{alpha:.12}),closeColorPressedSuccess:i(s,{alpha:.18}),borderWarning:`1px solid ${i(c,{alpha:.35})}`,textColorWarning:c,colorWarning:i(c,{alpha:.15}),colorBorderedWarning:i(c,{alpha:.12}),closeIconColorWarning:c,closeIconColorHoverWarning:c,closeIconColorPressedWarning:c,closeColorHoverWarning:i(c,{alpha:.12}),closeColorPressedWarning:i(c,{alpha:.18}),borderError:`1px solid ${i(l,{alpha:.23})}`,textColorError:l,colorError:i(l,{alpha:.1}),colorBorderedError:i(l,{alpha:.08}),closeIconColorError:l,closeIconColorHoverError:l,closeIconColorPressedError:l,closeColorHoverError:i(l,{alpha:.12}),closeColorPressedError:i(l,{alpha:.18})})}var ht={name:`Tag`,common:te,self:mt},gt={color:Object,type:{type:String,default:`default`},round:Boolean,size:String,closable:Boolean,disabled:{type:Boolean,default:void 0}},_t=f(`tag`,`
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
`,[R(`strong`,`
 font-weight: var(--n-font-weight-strong);
 `),E(`border`,`
 pointer-events: none;
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 border-radius: inherit;
 border: var(--n-border);
 transition: border-color .3s var(--n-bezier);
 `),E(`icon`,`
 display: flex;
 margin: 0 4px 0 0;
 color: var(--n-text-color);
 transition: color .3s var(--n-bezier);
 font-size: var(--n-avatar-size-override);
 `),E(`avatar`,`
 display: flex;
 margin: 0 6px 0 0;
 `),E(`close`,`
 margin: var(--n-close-margin);
 transition:
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 `),R(`round`,`
 padding: 0 calc(var(--n-height) / 3);
 border-radius: calc(var(--n-height) / 2);
 `,[E(`icon`,`
 margin: 0 4px 0 calc((var(--n-height) - 8px) / -2);
 `),E(`avatar`,`
 margin: 0 6px 0 calc((var(--n-height) - 8px) / -2);
 `),R(`closable`,`
 padding: 0 calc(var(--n-height) / 4) 0 calc(var(--n-height) / 3);
 `)]),R(`icon, avatar`,[R(`round`,`
 padding: 0 calc(var(--n-height) / 3) 0 calc(var(--n-height) / 2);
 `)]),R(`disabled`,`
 cursor: not-allowed !important;
 opacity: var(--n-opacity-disabled);
 `),R(`checkable`,`
 cursor: pointer;
 box-shadow: none;
 color: var(--n-text-color-checkable);
 background-color: var(--n-color-checkable);
 `,[M(`disabled`,[b(`&:hover`,`background-color: var(--n-color-hover-checkable);`,[M(`checked`,`color: var(--n-text-color-hover-checkable);`)]),b(`&:active`,`background-color: var(--n-color-pressed-checkable);`,[M(`checked`,`color: var(--n-text-color-pressed-checkable);`)])]),R(`checked`,`
 color: var(--n-text-color-checked);
 background-color: var(--n-color-checked);
 `,[M(`disabled`,[b(`&:hover`,`background-color: var(--n-color-checked-hover);`),b(`&:active`,`background-color: var(--n-color-checked-pressed);`)])])])]),vt=Object.assign(Object.assign(Object.assign({},c.props),gt),{bordered:{type:Boolean,default:void 0},checked:Boolean,checkable:Boolean,strong:Boolean,triggerClickOnClose:Boolean,onClose:[Array,Function],onMouseenter:Function,onMouseleave:Function,"onUpdate:checked":Function,onUpdateChecked:Function,internalCloseFocusable:{type:Boolean,default:!0},internalCloseIsButtonTag:{type:Boolean,default:!0},onCheckedChange:Function}),yt=u(`n-tag`),bt=A({name:`Tag`,props:vt,slots:Object,setup(e){let t=N(null),{mergedBorderedRef:n,mergedClsPrefixRef:r,inlineThemeDisabled:i,mergedRtlRef:a,mergedComponentPropsRef:o}=T(e),s=m(()=>e.size||o?.value?.Tag?.size||`medium`),l=c(`Tag`,`-tag`,_t,ht,e,r);g(yt,{roundRef:C(e,`round`)});function u(){if(!e.disabled&&e.checkable){let{checked:t,onCheckedChange:n,onUpdateChecked:r,"onUpdate:checked":i}=e;r&&r(!t),i&&i(!t),n&&n(!t)}}function d(t){if(e.triggerClickOnClose||t.stopPropagation(),!e.disabled){let{onClose:n}=e;n&&S(n,t)}}let f={setTextContent(e){let{value:n}=t;n&&(n.textContent=e)}},p=O(`Tag`,a,r),h=m(()=>{let{type:t,color:{color:r,textColor:i}={}}=e,a=s.value,{common:{cubicBezierEaseInOut:o},self:{padding:c,closeMargin:u,borderRadius:d,opacityDisabled:f,textColorCheckable:p,textColorHoverCheckable:m,textColorPressedCheckable:h,textColorChecked:g,colorCheckable:_,colorHoverCheckable:v,colorPressedCheckable:y,colorChecked:b,colorCheckedHover:x,colorCheckedPressed:S,closeBorderRadius:C,fontWeightStrong:w,[I(`colorBordered`,t)]:T,[I(`closeSize`,a)]:E,[I(`closeIconSize`,a)]:D,[I(`fontSize`,a)]:O,[I(`height`,a)]:k,[I(`color`,t)]:A,[I(`textColor`,t)]:j,[I(`border`,t)]:M,[I(`closeIconColor`,t)]:N,[I(`closeIconColorHover`,t)]:ee,[I(`closeIconColorPressed`,t)]:P,[I(`closeColorHover`,t)]:L,[I(`closeColorPressed`,t)]:R}}=l.value,z=F(u);return{"--n-font-weight-strong":w,"--n-avatar-size-override":`calc(${k} - 8px)`,"--n-bezier":o,"--n-border-radius":d,"--n-border":M,"--n-close-icon-size":D,"--n-close-color-pressed":R,"--n-close-color-hover":L,"--n-close-border-radius":C,"--n-close-icon-color":N,"--n-close-icon-color-hover":ee,"--n-close-icon-color-pressed":P,"--n-close-icon-color-disabled":N,"--n-close-margin-top":z.top,"--n-close-margin-right":z.right,"--n-close-margin-bottom":z.bottom,"--n-close-margin-left":z.left,"--n-close-size":E,"--n-color":r||(n.value?T:A),"--n-color-checkable":_,"--n-color-checked":b,"--n-color-checked-hover":x,"--n-color-checked-pressed":S,"--n-color-hover-checkable":v,"--n-color-pressed-checkable":y,"--n-font-size":O,"--n-height":k,"--n-opacity-disabled":f,"--n-padding":c,"--n-text-color":i||j,"--n-text-color-checkable":p,"--n-text-color-checked":g,"--n-text-color-hover-checkable":m,"--n-text-color-pressed-checkable":h}}),_=i?L(`tag`,m(()=>{let t=``,{type:r,color:{color:i,textColor:a}={}}=e;return t+=r[0],t+=s.value[0],i&&(t+=`a${w(i)}`),a&&(t+=`b${w(a)}`),n.value&&(t+=`c`),t}),h,e):void 0;return Object.assign(Object.assign({},f),{rtlEnabled:p,mergedClsPrefix:r,contentRef:t,mergedBordered:n,handleClick:u,handleCloseClick:d,cssVars:i?void 0:h,themeClass:_?.themeClass,onRender:_?.onRender})},render(){var e;let{mergedClsPrefix:t,rtlEnabled:n,closable:r,color:{borderColor:i}={},round:a,onRender:o,$slots:s}=this;o?.();let c=D(s.avatar,e=>e&&k(`div`,{class:`${t}-tag__avatar`},e)),l=D(s.icon,e=>e&&k(`div`,{class:`${t}-tag__icon`},e));return k(`div`,{class:[`${t}-tag`,this.themeClass,{[`${t}-tag--rtl`]:n,[`${t}-tag--strong`]:this.strong,[`${t}-tag--disabled`]:this.disabled,[`${t}-tag--checkable`]:this.checkable,[`${t}-tag--checked`]:this.checkable&&this.checked,[`${t}-tag--round`]:a,[`${t}-tag--avatar`]:c,[`${t}-tag--icon`]:l,[`${t}-tag--closable`]:r}],style:this.cssVars,onClick:this.handleClick,onMouseenter:this.onMouseenter,onMouseleave:this.onMouseleave},l||c,k(`span`,{class:`${t}-tag__content`,ref:`contentRef`},(e=this.$slots).default?.call(e)),!this.checkable&&r?k(de,{clsPrefix:t,class:`${t}-tag__close`,disabled:this.disabled,onClick:this.handleCloseClick,focusable:this.internalCloseFocusable,round:a,isButtonTag:this.internalCloseIsButtonTag,absolute:!0}):null,!this.checkable&&this.mergedBordered?k(`div`,{class:`${t}-tag__border`,style:{borderColor:i}}):null)}}),xt=b([f(`base-selection`,`
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
 `,[f(`base-loading`,`
 color: var(--n-loading-color);
 `),f(`base-selection-tags`,`min-height: var(--n-height);`),E(`border, state-border`,`
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
 `),E(`state-border`,`
 z-index: 1;
 border-color: #0000;
 `),f(`base-suffix`,`
 cursor: pointer;
 position: absolute;
 top: 50%;
 transform: translateY(-50%);
 right: 10px;
 `,[E(`arrow`,`
 font-size: var(--n-arrow-size);
 color: var(--n-arrow-color);
 transition: color .3s var(--n-bezier);
 `)]),f(`base-selection-overlay`,`
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
 `,[E(`wrapper`,`
 flex-basis: 0;
 flex-grow: 1;
 overflow: hidden;
 text-overflow: ellipsis;
 `)]),f(`base-selection-placeholder`,`
 color: var(--n-placeholder-color);
 `,[E(`inner`,`
 max-width: 100%;
 overflow: hidden;
 `)]),f(`base-selection-tags`,`
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
 `),f(`base-selection-label`,`
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
 `,[f(`base-selection-input`,`
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
 `,[E(`content`,`
 text-overflow: ellipsis;
 overflow: hidden;
 white-space: nowrap; 
 `)]),E(`render-label`,`
 color: var(--n-text-color);
 `)]),M(`disabled`,[b(`&:hover`,[E(`state-border`,`
 box-shadow: var(--n-box-shadow-hover);
 border: var(--n-border-hover);
 `)]),R(`focus`,[E(`state-border`,`
 box-shadow: var(--n-box-shadow-focus);
 border: var(--n-border-focus);
 `)]),R(`active`,[E(`state-border`,`
 box-shadow: var(--n-box-shadow-active);
 border: var(--n-border-active);
 `),f(`base-selection-label`,`background-color: var(--n-color-active);`),f(`base-selection-tags`,`background-color: var(--n-color-active);`)])]),R(`disabled`,`cursor: not-allowed;`,[E(`arrow`,`
 color: var(--n-arrow-color-disabled);
 `),f(`base-selection-label`,`
 cursor: not-allowed;
 background-color: var(--n-color-disabled);
 `,[f(`base-selection-input`,`
 cursor: not-allowed;
 color: var(--n-text-color-disabled);
 `),E(`render-label`,`
 color: var(--n-text-color-disabled);
 `)]),f(`base-selection-tags`,`
 cursor: not-allowed;
 background-color: var(--n-color-disabled);
 `),f(`base-selection-placeholder`,`
 cursor: not-allowed;
 color: var(--n-placeholder-color-disabled);
 `)]),f(`base-selection-input-tag`,`
 height: calc(var(--n-height) - 6px);
 line-height: calc(var(--n-height) - 6px);
 outline: none;
 display: none;
 position: relative;
 margin-bottom: 3px;
 max-width: 100%;
 vertical-align: bottom;
 `,[E(`input`,`
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
 `),E(`mirror`,`
 position: absolute;
 left: 0;
 top: 0;
 white-space: pre;
 visibility: hidden;
 user-select: none;
 -webkit-user-select: none;
 opacity: 0;
 `)]),[`warning`,`error`].map(e=>R(`${e}-status`,[E(`state-border`,`border: var(--n-border-${e});`),M(`disabled`,[b(`&:hover`,[E(`state-border`,`
 box-shadow: var(--n-box-shadow-hover-${e});
 border: var(--n-border-hover-${e});
 `)]),R(`active`,[E(`state-border`,`
 box-shadow: var(--n-box-shadow-active-${e});
 border: var(--n-border-active-${e});
 `),f(`base-selection-label`,`background-color: var(--n-color-active-${e});`),f(`base-selection-tags`,`background-color: var(--n-color-active-${e});`)]),R(`focus`,[E(`state-border`,`
 box-shadow: var(--n-box-shadow-focus-${e});
 border: var(--n-border-focus-${e});
 `)])])]))]),f(`base-selection-popover`,`
 margin-bottom: -3px;
 display: flex;
 flex-wrap: wrap;
 margin-right: -8px;
 `),f(`base-selection-tag-wrapper`,`
 max-width: 100%;
 display: inline-flex;
 padding: 0 7px 3px 0;
 `,[b(`&:last-child`,`padding-right: 0;`),f(`tag`,`
 font-size: 14px;
 max-width: 100%;
 `,[E(`content`,`
 line-height: 1.25;
 text-overflow: ellipsis;
 overflow: hidden;
 `)])])]),St=A({name:`InternalSelection`,props:Object.assign(Object.assign({},c.props),{clsPrefix:{type:String,required:!0},bordered:{type:Boolean,default:void 0},active:Boolean,pattern:{type:String,default:``},placeholder:String,selectedOption:{type:Object,default:null},selectedOptions:{type:Array,default:null},labelField:{type:String,default:`label`},valueField:{type:String,default:`value`},multiple:Boolean,filterable:Boolean,clearable:Boolean,disabled:Boolean,size:{type:String,default:`medium`},loading:Boolean,autofocus:Boolean,showArrow:{type:Boolean,default:!0},inputProps:Object,focused:Boolean,renderTag:Function,onKeydown:Function,onClick:Function,onBlur:Function,onFocus:Function,onDeleteOption:Function,maxTagCount:[String,Number],ellipsisTagPopoverProps:Object,onClear:Function,onPatternInput:Function,onPatternFocus:Function,onPatternBlur:Function,renderLabel:Function,status:String,inlineThemeDisabled:Boolean,ignoreComposition:{type:Boolean,default:!0},onResize:Function}),setup(e){let{mergedClsPrefixRef:t,mergedRtlRef:n}=T(e),r=O(`InternalSelection`,n,t),i=N(null),a=N(null),o=N(null),s=N(null),u=N(null),d=N(null),f=N(null),p=N(null),h=N(null),g=N(null),y=N(!1),b=N(!1),x=N(!1),S=c(`InternalSelection`,`-internal-selection`,xt,ve,e,C(e,`clsPrefix`)),w=m(()=>e.clearable&&!e.disabled&&(x.value||e.active)),E=m(()=>e.selectedOption?e.renderTag?e.renderTag({option:e.selectedOption,handleClose:()=>{}}):e.renderLabel?e.renderLabel(e.selectedOption,!0):Q(e.selectedOption[e.labelField],e.selectedOption,!0):e.placeholder),D=m(()=>{let t=e.selectedOption;if(t)return t[e.labelField]}),k=m(()=>e.multiple?!!(Array.isArray(e.selectedOptions)&&e.selectedOptions.length):e.selectedOption!==null);function A(){var t;let{value:n}=i;if(n){let{value:r}=a;r&&(r.style.width=`${n.offsetWidth}px`,e.maxTagCount!==`responsive`&&((t=h.value)==null||t.sync({showAllItemsBeforeCalculate:!1})))}}function j(){let{value:e}=g;e&&(e.style.display=`none`)}function M(){let{value:e}=g;e&&(e.style.display=`inline-block`)}v(C(e,`active`),e=>{e||j()}),v(C(e,`pattern`),()=>{e.multiple&&l(A)});function ee(t){let{onFocus:n}=e;n&&n(t)}function P(t){let{onBlur:n}=e;n&&n(t)}function R(t){let{onDeleteOption:n}=e;n&&n(t)}function z(t){let{onClear:n}=e;n&&n(t)}function B(t){let{onPatternInput:n}=e;n&&n(t)}function V(e){(!e.relatedTarget||!o.value?.contains(e.relatedTarget))&&ee(e)}function H(e){o.value?.contains(e.relatedTarget)||P(e)}function te(e){z(e)}function ne(){x.value=!0}function W(){x.value=!1}function re(t){!e.active||!e.filterable||t.target!==a.value&&t.preventDefault()}function G(e){R(e)}let K=N(!1);function q(t){if(t.key===`Backspace`&&!K.value&&!e.pattern.length){let{selectedOptions:t}=e;t?.length&&G(t[t.length-1])}}let J=null;function ie(t){let{value:n}=i;n&&(n.textContent=t.target.value,A()),e.ignoreComposition&&K.value?J=t:B(t)}function ae(){K.value=!0}function oe(){K.value=!1,e.ignoreComposition&&B(J),J=null}function se(t){var n;b.value=!0,(n=e.onPatternFocus)==null||n.call(e,t)}function ce(t){var n;b.value=!1,(n=e.onPatternBlur)==null||n.call(e,t)}function Y(){var t,n;if(e.filterable)b.value=!1,(t=d.value)==null||t.blur(),(n=a.value)==null||n.blur();else if(e.multiple){let{value:e}=s;e?.blur()}else{let{value:e}=u;e?.blur()}}function X(){var t,n,r;e.filterable?(b.value=!1,(t=d.value)==null||t.focus()):e.multiple?(n=s.value)==null||n.focus():(r=u.value)==null||r.focus()}function le(){let{value:e}=a;e&&(M(),e.focus())}function Z(){let{value:e}=a;e&&e.blur()}function ue(e){let{value:t}=f;t&&t.setTextContent(`+${e}`)}function de(){let{value:e}=p;return e}function fe(){return a.value}let pe=null;function me(){pe!==null&&window.clearTimeout(pe)}function he(){e.active||(me(),pe=window.setTimeout(()=>{k.value&&(y.value=!0)},100))}function ge(){me()}function _e(e){e||(me(),y.value=!1)}v(k,e=>{e||(y.value=!1)}),U(()=>{_(()=>{let t=d.value;t&&(e.disabled?t.removeAttribute(`tabindex`):t.tabIndex=b.value?-1:0)})}),xe(o,e.onResize);let{inlineThemeDisabled:$}=e,ye=m(()=>{let{size:t}=e,{common:{cubicBezierEaseInOut:n},self:{fontWeight:r,borderRadius:i,color:a,placeholderColor:o,textColor:s,paddingSingle:c,paddingMultiple:l,caretColor:u,colorDisabled:d,textColorDisabled:f,placeholderColorDisabled:p,colorActive:m,boxShadowFocus:h,boxShadowActive:g,boxShadowHover:_,border:v,borderFocus:y,borderHover:b,borderActive:x,arrowColor:C,arrowColorDisabled:w,loadingColor:T,colorActiveWarning:E,boxShadowFocusWarning:D,boxShadowActiveWarning:O,boxShadowHoverWarning:k,borderWarning:A,borderFocusWarning:j,borderHoverWarning:M,borderActiveWarning:N,colorActiveError:ee,boxShadowFocusError:P,boxShadowActiveError:L,boxShadowHoverError:R,borderError:z,borderFocusError:B,borderHoverError:V,borderActiveError:H,clearColor:te,clearColorHover:U,clearColorPressed:ne,clearSize:W,arrowSize:re,[I(`height`,t)]:G,[I(`fontSize`,t)]:K}}=S.value,q=F(c),J=F(l);return{"--n-bezier":n,"--n-border":v,"--n-border-active":x,"--n-border-focus":y,"--n-border-hover":b,"--n-border-radius":i,"--n-box-shadow-active":g,"--n-box-shadow-focus":h,"--n-box-shadow-hover":_,"--n-caret-color":u,"--n-color":a,"--n-color-active":m,"--n-color-disabled":d,"--n-font-size":K,"--n-height":G,"--n-padding-single-top":q.top,"--n-padding-multiple-top":J.top,"--n-padding-single-right":q.right,"--n-padding-multiple-right":J.right,"--n-padding-single-left":q.left,"--n-padding-multiple-left":J.left,"--n-padding-single-bottom":q.bottom,"--n-padding-multiple-bottom":J.bottom,"--n-placeholder-color":o,"--n-placeholder-color-disabled":p,"--n-text-color":s,"--n-text-color-disabled":f,"--n-arrow-color":C,"--n-arrow-color-disabled":w,"--n-loading-color":T,"--n-color-active-warning":E,"--n-box-shadow-focus-warning":D,"--n-box-shadow-active-warning":O,"--n-box-shadow-hover-warning":k,"--n-border-warning":A,"--n-border-focus-warning":j,"--n-border-hover-warning":M,"--n-border-active-warning":N,"--n-color-active-error":ee,"--n-box-shadow-focus-error":P,"--n-box-shadow-active-error":L,"--n-box-shadow-hover-error":R,"--n-border-error":z,"--n-border-focus-error":B,"--n-border-hover-error":V,"--n-border-active-error":H,"--n-clear-size":W,"--n-clear-color":te,"--n-clear-color-hover":U,"--n-clear-color-pressed":ne,"--n-arrow-size":re,"--n-font-weight":r}}),be=$?L(`internal-selection`,m(()=>e.size[0]),ye,e):void 0;return{mergedTheme:S,mergedClearable:w,mergedClsPrefix:t,rtlEnabled:r,patternInputFocused:b,filterablePlaceholder:E,label:D,selected:k,showTagsPanel:y,isComposing:K,counterRef:f,counterWrapperRef:p,patternInputMirrorRef:i,patternInputRef:a,selfRef:o,multipleElRef:s,singleElRef:u,patternInputWrapperRef:d,overflowRef:h,inputTagElRef:g,handleMouseDown:re,handleFocusin:V,handleClear:te,handleMouseEnter:ne,handleMouseLeave:W,handleDeleteOption:G,handlePatternKeyDown:q,handlePatternInputInput:ie,handlePatternInputBlur:ce,handlePatternInputFocus:se,handleMouseEnterCounter:he,handleMouseLeaveCounter:ge,handleFocusout:H,handleCompositionEnd:oe,handleCompositionStart:ae,onPopoverUpdateShow:_e,focus:X,focusInput:le,blur:Y,blurInput:Z,updateCounter:ue,getCounter:de,getTail:fe,renderLabel:e.renderLabel,cssVars:$?void 0:ye,themeClass:be?.themeClass,onRender:be?.onRender}},render(){let{status:e,multiple:t,size:n,disabled:r,filterable:i,maxTagCount:a,bordered:o,clsPrefix:s,ellipsisTagPopoverProps:c,onRender:l,renderTag:u,renderLabel:d}=this;l?.();let f=a===`responsive`,p=typeof a==`number`,m=f||p,h=k(B,null,{default:()=>k(X,{clsPrefix:s,loading:this.loading,showArrow:this.showArrow,showClear:this.mergedClearable&&this.selected,onClear:this.handleClear},{default:()=>{var e;return(e=this.$slots).arrow?.call(e)}})}),g;if(t){let{labelField:e}=this,t=t=>k(`div`,{class:`${s}-base-selection-tag-wrapper`,key:t.value},u?u({option:t,handleClose:()=>{this.handleDeleteOption(t)}}):k(bt,{size:n,closable:!t.disabled,disabled:r,onClose:()=>{this.handleDeleteOption(t)},internalCloseIsButtonTag:!1,internalCloseFocusable:!1},{default:()=>d?d(t,!0):Q(t[e],t,!0)})),o=()=>(p?this.selectedOptions.slice(0,a):this.selectedOptions).map(t),l=i?k(`div`,{class:`${s}-base-selection-input-tag`,ref:`inputTagElRef`,key:`__input-tag__`},k(`input`,Object.assign({},this.inputProps,{ref:`patternInputRef`,tabindex:-1,disabled:r,value:this.pattern,autofocus:this.autofocus,class:`${s}-base-selection-input-tag__input`,onBlur:this.handlePatternInputBlur,onFocus:this.handlePatternInputFocus,onKeydown:this.handlePatternKeyDown,onInput:this.handlePatternInputInput,onCompositionstart:this.handleCompositionStart,onCompositionend:this.handleCompositionEnd})),k(`span`,{ref:`patternInputMirrorRef`,class:`${s}-base-selection-input-tag__mirror`},this.pattern)):null,_=f?()=>k(`div`,{class:`${s}-base-selection-tag-wrapper`,ref:`counterWrapperRef`},k(bt,{size:n,ref:`counterRef`,onMouseenter:this.handleMouseEnterCounter,onMouseleave:this.handleMouseLeaveCounter,disabled:r})):void 0,v;if(p){let e=this.selectedOptions.length-a;e>0&&(v=k(`div`,{class:`${s}-base-selection-tag-wrapper`,key:`__counter__`},k(bt,{size:n,ref:`counterRef`,onMouseenter:this.handleMouseEnterCounter,disabled:r},{default:()=>`+${e}`})))}let y=f?i?k(be,{ref:`overflowRef`,updateCounter:this.updateCounter,getCounter:this.getCounter,getTail:this.getTail,style:{width:`100%`,display:`flex`,overflow:`hidden`}},{default:o,counter:_,tail:()=>l}):k(be,{ref:`overflowRef`,updateCounter:this.updateCounter,getCounter:this.getCounter,style:{width:`100%`,display:`flex`,overflow:`hidden`}},{default:o,counter:_}):p&&v?o().concat(v):o(),b=m?()=>k(`div`,{class:`${s}-base-selection-popover`},f?o():this.selectedOptions.map(t)):void 0,x=m?Object.assign({show:this.showTagsPanel,trigger:`hover`,overlap:!0,placement:`top`,width:`trigger`,onUpdateShow:this.onPopoverUpdateShow,theme:this.mergedTheme.peers.Popover,themeOverrides:this.mergedTheme.peerOverrides.Popover},c):null,S=!this.selected&&(!this.active||!this.pattern&&!this.isComposing)?k(`div`,{class:`${s}-base-selection-placeholder ${s}-base-selection-overlay`},k(`div`,{class:`${s}-base-selection-placeholder__inner`},this.placeholder)):null,C=i?k(`div`,{ref:`patternInputWrapperRef`,class:`${s}-base-selection-tags`},y,f?null:l,h):k(`div`,{ref:`multipleElRef`,class:`${s}-base-selection-tags`,tabindex:r?void 0:0},y,h);g=k(V,null,m?k(Z,Object.assign({},x,{scrollable:!0,style:`max-height: calc(var(--v-target-height) * 6.6);`}),{trigger:()=>C,default:b}):C,S)}else if(i){let e=this.pattern||this.isComposing,t=this.active?!e:!this.selected,n=this.active?!1:this.selected;g=k(`div`,{ref:`patternInputWrapperRef`,class:`${s}-base-selection-label`,title:this.patternInputFocused?void 0:Se(this.label)},k(`input`,Object.assign({},this.inputProps,{ref:`patternInputRef`,class:`${s}-base-selection-input`,value:this.active?this.pattern:``,placeholder:``,readonly:r,disabled:r,tabindex:-1,autofocus:this.autofocus,onFocus:this.handlePatternInputFocus,onBlur:this.handlePatternInputBlur,onInput:this.handlePatternInputInput,onCompositionstart:this.handleCompositionStart,onCompositionend:this.handleCompositionEnd})),n?k(`div`,{class:`${s}-base-selection-label__render-label ${s}-base-selection-overlay`,key:`input`},k(`div`,{class:`${s}-base-selection-overlay__wrapper`},u?u({option:this.selectedOption,handleClose:()=>{}}):d?d(this.selectedOption,!0):Q(this.label,this.selectedOption,!0))):null,t?k(`div`,{class:`${s}-base-selection-placeholder ${s}-base-selection-overlay`,key:`placeholder`},k(`div`,{class:`${s}-base-selection-overlay__wrapper`},this.filterablePlaceholder)):null,h)}else g=k(`div`,{ref:`singleElRef`,class:`${s}-base-selection-label`,tabindex:this.disabled?void 0:0},this.label===void 0?k(`div`,{class:`${s}-base-selection-placeholder ${s}-base-selection-overlay`,key:`placeholder`},k(`div`,{class:`${s}-base-selection-placeholder__inner`},this.placeholder)):k(`div`,{class:`${s}-base-selection-input`,title:Se(this.label),key:`input`},k(`div`,{class:`${s}-base-selection-input__content`},u?u({option:this.selectedOption,handleClose:()=>{}}):d?d(this.selectedOption,!0):Q(this.label,this.selectedOption,!0))),h);return k(`div`,{ref:`selfRef`,class:[`${s}-base-selection`,this.rtlEnabled&&`${s}-base-selection--rtl`,this.themeClass,e&&`${s}-base-selection--${e}-status`,{[`${s}-base-selection--active`]:this.active,[`${s}-base-selection--selected`]:this.selected||this.active&&this.pattern,[`${s}-base-selection--disabled`]:this.disabled,[`${s}-base-selection--multiple`]:this.multiple,[`${s}-base-selection--focus`]:this.focused}],style:this.cssVars,onClick:this.onClick,onMouseenter:this.handleMouseEnter,onMouseleave:this.handleMouseLeave,onKeydown:this.onKeydown,onFocusin:this.handleFocusin,onFocusout:this.handleFocusout,onMousedown:this.handleMouseDown},g,o?k(`div`,{class:`${s}-base-selection__border`}):null,o?k(`div`,{class:`${s}-base-selection__state-border`}):null)}});function Ct(e){return e.type===`group`}function wt(e){return e.type===`ignored`}function Tt(e,t){try{return!!(1+t.toString().toLowerCase().indexOf(e.trim().toLowerCase()))}catch{return!1}}function Et(e,t){return{getIsGroup:Ct,getIgnored:wt,getKey(t){return Ct(t)?t.name||t.key||`key-required`:t[e]},getChildren(e){return e[t]}}}function Dt(e,t,n,r){if(!t)return e;function i(e){if(!Array.isArray(e))return[];let a=[];for(let o of e)if(Ct(o)){let e=i(o[r]);e.length&&a.push(Object.assign({},o,{[r]:e}))}else if(wt(o))continue;else t(n,o)&&a.push(o);return a}return i(e)}function Ot(e,t,n){let r=new Map;return e.forEach(e=>{Ct(e)?e[n].forEach(e=>{r.set(e[t],e)}):r.set(e[t],e)}),r}var kt=b([f(`select`,`
 z-index: auto;
 outline: none;
 width: 100%;
 position: relative;
 font-weight: var(--n-font-weight);
 `),f(`select-menu`,`
 margin: 4px 0;
 box-shadow: var(--n-menu-box-shadow);
 `,[_e({originalTransition:`background-color .3s var(--n-bezier), box-shadow .3s var(--n-bezier)`})])]),At=A({name:`Select`,props:Object.assign(Object.assign({},c.props),{to:W.propTo,bordered:{type:Boolean,default:void 0},clearable:Boolean,clearCreatedOptionsOnClear:{type:Boolean,default:!0},clearFilterAfterSelect:{type:Boolean,default:!0},options:{type:Array,default:()=>[]},defaultValue:{type:[String,Number,Array],default:null},keyboard:{type:Boolean,default:!0},value:[String,Number,Array],placeholder:String,menuProps:Object,multiple:Boolean,size:String,menuSize:{type:String},filterable:Boolean,disabled:{type:Boolean,default:void 0},remote:Boolean,loading:Boolean,filter:Function,placement:{type:String,default:`bottom-start`},widthMode:{type:String,default:`trigger`},tag:Boolean,onCreate:Function,fallbackOption:{type:[Function,Boolean],default:void 0},show:{type:Boolean,default:void 0},showArrow:{type:Boolean,default:!0},maxTagCount:[Number,String],ellipsisTagPopoverProps:Object,consistentMenuWidth:{type:Boolean,default:!0},virtualScroll:{type:Boolean,default:!0},labelField:{type:String,default:`label`},valueField:{type:String,default:`value`},childrenField:{type:String,default:`children`},renderLabel:Function,renderOption:Function,renderTag:Function,"onUpdate:value":[Function,Array],inputProps:Object,nodeProps:Function,ignoreComposition:{type:Boolean,default:!0},showOnFocus:Boolean,onUpdateValue:[Function,Array],onBlur:[Function,Array],onClear:[Function,Array],onFocus:[Function,Array],onScroll:[Function,Array],onSearch:[Function,Array],onUpdateShow:[Function,Array],"onUpdate:show":[Function,Array],displayDirective:{type:String,default:`show`},resetMenuOnOptionsChange:{type:Boolean,default:!0},status:String,showCheckmark:{type:Boolean,default:!0},scrollbarProps:Object,onChange:[Function,Array],items:Array}),slots:Object,setup(e){let{mergedClsPrefixRef:t,mergedBorderedRef:r,namespaceRef:i,inlineThemeDisabled:a,mergedComponentPropsRef:o}=T(e),s=c(`Select`,`-select`,kt,ge,e,t),l=N(e.defaultValue),u=re(C(e,`value`),l),d=N(!1),f=N(``),p=le(e,[`items`,`options`]),h=N([]),g=N([]),_=m(()=>g.value.concat(h.value).concat(p.value)),b=m(()=>{let{filter:t}=e;if(t)return t;let{labelField:n,valueField:r}=e;return(e,t)=>{if(!t)return!1;let i=t[n];if(typeof i==`string`)return Tt(e,i);let a=t[r];return typeof a==`string`?Tt(e,a):typeof a==`number`?Tt(e,String(a)):!1}}),x=m(()=>{if(e.remote)return p.value;{let{value:t}=_,{value:n}=f;return!n.length||!e.filterable?t:Dt(t,b.value,n,e.childrenField)}}),w=m(()=>{let{valueField:t,childrenField:n}=e,r=Et(t,n);return ot(x.value,r)}),E=m(()=>Ot(_.value,e.valueField,e.childrenField)),D=N(!1),O=re(C(e,`show`),D),k=N(null),A=N(null),j=N(null),{localeRef:M}=oe(`Select`),P=m(()=>e.placeholder??M.value.placeholder),F=[],I=N(new Map),R=m(()=>{let{fallbackOption:t}=e;if(t===void 0){let{labelField:t,valueField:n}=e;return e=>({[t]:String(e),[n]:e})}return t===!1?!1:e=>Object.assign(t(e),{value:e})});function z(t){let n=e.remote,{value:r}=I,{value:i}=E,{value:a}=R,o=[];return t.forEach(e=>{if(i.has(e))o.push(i.get(e));else if(n&&r.has(e))o.push(r.get(e));else if(a){let t=a(e);t&&o.push(t)}}),o}let B=m(()=>{if(e.multiple){let{value:e}=u;return Array.isArray(e)?z(e):[]}return null}),V=m(()=>{let{value:t}=u;return!e.multiple&&!Array.isArray(t)?t===null?null:z([t])[0]||null:null}),H=ee(e,{mergedSize:t=>{let{size:n}=e;if(n)return n;let{mergedSize:r}=t||{};return r?.value?r.value:o?.value?.Select?.size||`medium`}}),{mergedSizeRef:te,mergedDisabledRef:U,mergedStatusRef:ne}=H;function G(t,n){let{onChange:r,"onUpdate:value":i,onUpdateValue:a}=e,{nTriggerFormChange:o,nTriggerFormInput:s}=H;r&&S(r,t,n),a&&S(a,t,n),i&&S(i,t,n),l.value=t,o(),s()}function K(t){let{onBlur:n}=e,{nTriggerFormBlur:r}=H;n&&S(n,t),r()}function q(){let{onClear:t}=e;t&&S(t)}function J(t){let{onFocus:n,showOnFocus:r}=e,{nTriggerFormFocus:i}=H;n&&S(n,t),i(),r&&X()}function ie(t){let{onSearch:n}=e;n&&S(n,t)}function ae(t){let{onScroll:n}=e;n&&S(n,t)}function se(){var t;let{remote:n,multiple:r}=e;if(n){let{value:n}=I;if(r){let{valueField:r}=e;(t=B.value)==null||t.forEach(e=>{n.set(e[r],e)})}else{let t=V.value;t&&n.set(t[e.valueField],t)}}}function ce(t){let{onUpdateShow:n,"onUpdate:show":r}=e;n&&S(n,t),r&&S(r,t),D.value=t}function X(){U.value||(ce(!0),D.value=!0,e.filterable&&je())}function Z(){ce(!1)}function ue(){f.value=``,g.value=F}let de=N(!1);function fe(){e.filterable&&(de.value=!0)}function Q(){e.filterable&&(de.value=!1,O.value||ue())}function pe(){U.value||(O.value?e.filterable?je():Z():X())}function me(e){(j.value?.selfRef)?.contains(e.relatedTarget)||(d.value=!1,K(e),Z())}function _e(e){J(e),d.value=!0}function ve(){d.value=!0}function $(e){k.value?.$el.contains(e.relatedTarget)||(d.value=!1,K(e),Z())}function ye(){var e;(e=k.value)==null||e.focus(),Z()}function be(e){O.value&&(k.value?.$el.contains(y(e))||Z())}function xe(t){if(!Array.isArray(t))return[];if(R.value)return Array.from(t);{let{remote:n}=e,{value:r}=E;if(n){let{value:e}=I;return t.filter(t=>r.has(t)||e.has(t))}else return t.filter(e=>r.has(e))}}function Se(e){Ce(e.rawNode)}function Ce(t){if(U.value)return;let{tag:n,remote:r,clearFilterAfterSelect:i,valueField:a}=e;if(n&&!r){let{value:e}=g,t=e[0]||null;if(t){let e=h.value;e.length?e.push(t):h.value=[t],g.value=F}}if(r&&I.value.set(t[a],t),e.multiple){let e=xe(u.value),o=e.findIndex(e=>e===t[a]);if(~o){if(e.splice(o,1),n&&!r){let e=we(t[a]);~e&&(h.value.splice(e,1),i&&(f.value=``))}}else e.push(t[a]),i&&(f.value=``);G(e,z(e))}else{if(n&&!r){let e=we(t[a]);~e?h.value=[h.value[e]]:h.value=F}Ae(),Z(),G(t[a],t)}}function we(t){return h.value.findIndex(n=>n[e.valueField]===t)}function Te(t){O.value||X();let{value:n}=t.target;f.value=n;let{tag:r,remote:i}=e;if(ie(n),r&&!i){if(!n){g.value=F;return}let{onCreate:t}=e,r=t?t(n):{[e.labelField]:n,[e.valueField]:n},{valueField:i,labelField:a}=e;p.value.some(e=>e[i]===r[i]||e[a]===r[a])||h.value.some(e=>e[i]===r[i]||e[a]===r[a])?g.value=F:g.value=[r]}}function Ee(t){t.stopPropagation();let{multiple:n,tag:r,remote:i,clearCreatedOptionsOnClear:a}=e;!n&&e.filterable&&Z(),r&&!i&&a&&(h.value=F),q(),n?G([],[]):G(null,null)}function De(e){!Y(e,`action`)&&!Y(e,`empty`)&&!Y(e,`header`)&&e.preventDefault()}function Oe(e){ae(e)}function ke(t){var n,r,i;if(!e.keyboard){t.preventDefault();return}switch(t.key){case` `:if(e.filterable)break;t.preventDefault();case`Enter`:if(!k.value?.isComposing){if(O.value){let t=j.value?.getPendingTmNode();t?Se(t):e.filterable||(Z(),Ae())}else if(X(),e.tag&&de.value){let t=g.value[0];if(t){let n=t[e.valueField],{value:r}=u;e.multiple&&Array.isArray(r)&&r.includes(n)||Ce(t)}}}t.preventDefault();break;case`ArrowUp`:if(t.preventDefault(),e.loading)return;O.value&&((n=j.value)==null||n.prev());break;case`ArrowDown`:if(t.preventDefault(),e.loading)return;O.value?(r=j.value)==null||r.next():X();break;case`Escape`:O.value&&(he(t),Z()),(i=k.value)==null||i.focus();break}}function Ae(){var e;(e=k.value)==null||e.focus()}function je(){var e;(e=k.value)==null||e.focusInput()}function Me(){var e;O.value&&((e=A.value)==null||e.syncPosition())}se(),v(C(e,`options`),se);let Ne={focus:()=>{var e;(e=k.value)==null||e.focus()},focusInput:()=>{var e;(e=k.value)==null||e.focusInput()},blur:()=>{var e;(e=k.value)==null||e.blur()},blurInput:()=>{var e;(e=k.value)==null||e.blurInput()}},Pe=m(()=>{let{self:{menuBoxShadow:e}}=s.value;return{"--n-menu-box-shadow":e}}),Fe=a?L(`select`,void 0,Pe,e):void 0;return Object.assign(Object.assign({},Ne),{mergedStatus:ne,mergedClsPrefix:t,mergedBordered:r,namespace:i,treeMate:w,isMounted:n(),triggerRef:k,menuRef:j,pattern:f,uncontrolledShow:D,mergedShow:O,adjustedTo:W(e),uncontrolledValue:l,mergedValue:u,followerRef:A,localizedPlaceholder:P,selectedOption:V,selectedOptions:B,mergedSize:te,mergedDisabled:U,focused:d,activeWithoutMenuOpen:de,inlineThemeDisabled:a,onTriggerInputFocus:fe,onTriggerInputBlur:Q,handleTriggerOrMenuResize:Me,handleMenuFocus:ve,handleMenuBlur:$,handleMenuTabOut:ye,handleTriggerClick:pe,handleToggle:Se,handleDeleteOption:Ce,handlePatternInput:Te,handleClear:Ee,handleTriggerBlur:me,handleTriggerFocus:_e,handleKeydown:ke,handleMenuAfterLeave:ue,handleMenuClickOutside:be,handleMenuScroll:Oe,handleMenuKeydown:ke,handleMenuMousedown:De,mergedTheme:s,cssVars:a?void 0:Pe,themeClass:Fe?.themeClass,onRender:Fe?.onRender})},render(){return k(`div`,{class:`${this.mergedClsPrefix}-select`},k(ie,null,{default:()=>[k(q,null,{default:()=>k(St,{ref:`triggerRef`,inlineThemeDisabled:this.inlineThemeDisabled,status:this.mergedStatus,inputProps:this.inputProps,clsPrefix:this.mergedClsPrefix,showArrow:this.showArrow,maxTagCount:this.maxTagCount,ellipsisTagPopoverProps:this.ellipsisTagPopoverProps,bordered:this.mergedBordered,active:this.activeWithoutMenuOpen||this.mergedShow,pattern:this.pattern,placeholder:this.localizedPlaceholder,selectedOption:this.selectedOption,selectedOptions:this.selectedOptions,multiple:this.multiple,renderTag:this.renderTag,renderLabel:this.renderLabel,filterable:this.filterable,clearable:this.clearable,disabled:this.mergedDisabled,size:this.mergedSize,theme:this.mergedTheme.peers.InternalSelection,labelField:this.labelField,valueField:this.valueField,themeOverrides:this.mergedTheme.peerOverrides.InternalSelection,loading:this.loading,focused:this.focused,onClick:this.handleTriggerClick,onDeleteOption:this.handleDeleteOption,onPatternInput:this.handlePatternInput,onClear:this.handleClear,onBlur:this.handleTriggerBlur,onFocus:this.handleTriggerFocus,onKeydown:this.handleKeydown,onPatternBlur:this.onTriggerInputBlur,onPatternFocus:this.onTriggerInputFocus,onResize:this.handleTriggerOrMenuResize,ignoreComposition:this.ignoreComposition},{arrow:()=>{var e;return[(e=this.$slots).arrow?.call(e)]}})}),k(J,{ref:`followerRef`,show:this.mergedShow,to:this.adjustedTo,teleportDisabled:this.adjustedTo===W.tdkey,containerClass:this.namespace,width:this.consistentMenuWidth?`target`:void 0,minWidth:`target`,placement:this.placement},{default:()=>k(z,{name:`fade-in-scale-up-transition`,appear:this.isMounted,onAfterLeave:this.handleMenuAfterLeave},{default:()=>{var e;return this.mergedShow||this.displayDirective===`show`?((e=this.onRender)==null||e.call(this),d(k(pt,Object.assign({},this.menuProps,{ref:`menuRef`,onResize:this.handleTriggerOrMenuResize,inlineThemeDisabled:this.inlineThemeDisabled,virtualScroll:this.consistentMenuWidth&&this.virtualScroll,class:[`${this.mergedClsPrefix}-select-menu`,this.themeClass,this.menuProps?.class],clsPrefix:this.mergedClsPrefix,focusable:!0,labelField:this.labelField,valueField:this.valueField,autoPending:!0,nodeProps:this.nodeProps,theme:this.mergedTheme.peers.InternalSelectMenu,themeOverrides:this.mergedTheme.peerOverrides.InternalSelectMenu,treeMate:this.treeMate,multiple:this.multiple,size:this.menuSize,renderOption:this.renderOption,renderLabel:this.renderLabel,value:this.mergedValue,style:[this.menuProps?.style,this.cssVars],onToggle:this.handleToggle,onScroll:this.handleMenuScroll,onFocus:this.handleMenuFocus,onBlur:this.handleMenuBlur,onKeydown:this.handleMenuKeydown,onTabOut:this.handleMenuTabOut,onMousedown:this.handleMenuMousedown,show:this.mergedShow,showCheckmark:this.showCheckmark,resetMenuOnOptionsChange:this.resetMenuOnOptionsChange,scrollbarProps:this.scrollbarProps}),{empty:()=>{var e;return[(e=this.$slots).empty?.call(e)]},header:()=>{var e;return[(e=this.$slots).header?.call(e)]},action:()=>{var e;return[(e=this.$slots).action?.call(e)]}}),this.displayDirective===`show`?[[j,this.mergedShow],[t,this.handleMenuClickOutside,void 0,{capture:!0}]]:[[t,this.handleMenuClickOutside,void 0,{capture:!0}]])):null}})})]}))}});export{At as t};
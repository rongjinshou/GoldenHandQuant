import{D as e,E as t,T as n,_ as r,c as i,d as a,g as o,l as s,m as c,o as l,p as u,r as d,u as f,v as p,y as m}from"./PageHeader-Bs7bFj1j.js";import{a as h,c as g,l as _,n as v,r as y,t as b,u as x}from"./Suffix-DIYhYpiI.js";import{r as S,s as C}from"./GlossaryTip-YndzWCnm.js";import{$n as w,A as ee,Cn as T,Dn as E,F as D,Gt as O,H as k,Jt as A,Kn as j,L as te,Ln as M,N as ne,Nn as N,P,Q as F,Sn as I,T as re,Wn as L,Wt as ie,X as R,Xn as ae,_n as z,an as oe,ar as B,bn as V,dr as H,fn as U,gr as W,hn as se,in as ce,j as le,kn as ue,ln as G,nn as de,pn as K,pr as fe,qn as q,qt as J,rn as pe,sr as Y,tn as me,tr as he,tt as ge,ur as _e,vn as X,xn as Z,yr as Q,z as ve}from"./index-ezQMSb60.js";var $=`v-hidden`,ye=u(`[v-hidden]`,{display:`none!important`}),be=L({name:`Overflow`,props:{getCounter:Function,getTail:Function,updateCounter:Function,onUpdateCount:Function,onUpdateOverflow:Function},setup(e,{slots:t}){let n=W(null),r=W(null);function i(i){let{value:a}=n,{getCounter:o,getTail:s}=e,c;if(c=o===void 0?r.value:o(),!a||!c)return;c.hasAttribute($)&&c.removeAttribute($);let{children:l}=a;if(i.showAllItemsBeforeCalculate)for(let e of l)e.hasAttribute($)&&e.removeAttribute($);let u=a.offsetWidth,d=[],f=t.tail?s?.():null,p=f?f.offsetWidth:0,m=!1,h=a.children.length-+!!t.tail;for(let t=0;t<h-1;++t){if(t<0)continue;let n=l[t];if(m){n.hasAttribute($)||n.setAttribute($,``);continue}else n.hasAttribute($)&&n.removeAttribute($);let r=n.offsetWidth;if(p+=r,d[t]=r,p>u){let{updateCounter:n}=e;for(let r=t;r>=0;--r){let i=h-1-r;n===void 0?c.textContent=`${i}`:n(i);let a=c.offsetWidth;if(p-=d[r],p+a<=u||r===0){m=!0,t=r-1,f&&(t===-1?(f.style.maxWidth=`${u-a}px`,f.style.boxSizing=`border-box`):f.style.maxWidth=``);let{onUpdateCount:n}=e;n&&n(i);break}}}}let{onUpdateOverflow:g}=e;m?g!==void 0&&g(!0):(g!==void 0&&g(!1),c.setAttribute($,``))}let a=de();return ye.mount({id:`vueuc/overflow`,head:!0,anchorMetaName:c,ssr:a}),he(()=>i({showAllItemsBeforeCalculate:!1})),{selfRef:n,counterRef:r,sync:i}},render(){let{$slots:e}=this;return ae(()=>this.sync({showAllItemsBeforeCalculate:!1})),j(`div`,{class:`v-overflow`,ref:`selfRef`},[Y(e,`default`),e.counter?e.counter():j(`span`,{style:{display:`inline-block`},ref:`counterRef`}),e.tail?e.tail():null])}});function xe(e,t){t&&(he(()=>{let{value:n}=e;n&&me.registerHandler(n,t)}),_e(e,(e,t)=>{t&&me.unregisterHandler(t)},{deep:!1}),w(()=>{let{value:t}=e;t&&me.unregisterHandler(t)}))}function Se(e){switch(typeof e){case`string`:return e||void 0;case`number`:return String(e);default:return}}function Ce(e){let t=e.filter(e=>e!==void 0);if(t.length!==0)return t.length===1?t[0]:t=>{e.forEach(e=>{e&&e(t)})}}var we=L({name:`Checkmark`,render(){return j(`svg`,{xmlns:`http://www.w3.org/2000/svg`,viewBox:`0 0 16 16`},j(`g`,{fill:`none`},j(`path`,{d:`M14.046 3.486a.75.75 0 0 1-.032 1.06l-7.93 7.474a.85.85 0 0 1-1.188-.022l-2.68-2.72a.75.75 0 1 1 1.068-1.053l2.234 2.267l7.468-7.038a.75.75 0 0 1 1.06.032z`,fill:`currentColor`})))}}),Te=L({name:`Empty`,render(){return j(`svg`,{viewBox:`0 0 28 28`,fill:`none`,xmlns:`http://www.w3.org/2000/svg`},j(`path`,{d:`M26 7.5C26 11.0899 23.0899 14 19.5 14C15.9101 14 13 11.0899 13 7.5C13 3.91015 15.9101 1 19.5 1C23.0899 1 26 3.91015 26 7.5ZM16.8536 4.14645C16.6583 3.95118 16.3417 3.95118 16.1464 4.14645C15.9512 4.34171 15.9512 4.65829 16.1464 4.85355L18.7929 7.5L16.1464 10.1464C15.9512 10.3417 15.9512 10.6583 16.1464 10.8536C16.3417 11.0488 16.6583 11.0488 16.8536 10.8536L19.5 8.20711L22.1464 10.8536C22.3417 11.0488 22.6583 11.0488 22.8536 10.8536C23.0488 10.6583 23.0488 10.3417 22.8536 10.1464L20.2071 7.5L22.8536 4.85355C23.0488 4.65829 23.0488 4.34171 22.8536 4.14645C22.6583 3.95118 22.3417 3.95118 22.1464 4.14645L19.5 6.79289L16.8536 4.14645Z`,fill:`currentColor`}),j(`path`,{d:`M25 22.75V12.5991C24.5572 13.0765 24.053 13.4961 23.5 13.8454V16H17.5L17.3982 16.0068C17.0322 16.0565 16.75 16.3703 16.75 16.75C16.75 18.2688 15.5188 19.5 14 19.5C12.4812 19.5 11.25 18.2688 11.25 16.75L11.2432 16.6482C11.1935 16.2822 10.8797 16 10.5 16H4.5V7.25C4.5 6.2835 5.2835 5.5 6.25 5.5H12.2696C12.4146 4.97463 12.6153 4.47237 12.865 4H6.25C4.45507 4 3 5.45507 3 7.25V22.75C3 24.5449 4.45507 26 6.25 26H21.75C23.5449 26 25 24.5449 25 22.75ZM4.5 22.75V17.5H9.81597L9.85751 17.7041C10.2905 19.5919 11.9808 21 14 21L14.215 20.9947C16.2095 20.8953 17.842 19.4209 18.184 17.5H23.5V22.75C23.5 23.7165 22.7165 24.5 21.75 24.5H6.25C5.2835 24.5 4.5 23.7165 4.5 22.75Z`,fill:`currentColor`}))}});function Ee(e){return Array.isArray(e)?e:[e]}var De={STOP:`STOP`};function Oe(e,t){let n=t(e);e.children!==void 0&&n!==De.STOP&&e.children.forEach(e=>Oe(e,t))}function ke(e,t={}){let{preserveGroup:n=!1}=t,r=[],i=n?e=>{e.isLeaf||(r.push(e.key),a(e.children))}:e=>{e.isLeaf||(e.isGroup||r.push(e.key),a(e.children))};function a(e){e.forEach(i)}return a(e),r}function Ae(e,t){let{isLeaf:n}=e;return n===void 0?!t(e):n}function je(e){return e.children}function Me(e){return e.key}function Ne(){return!1}function Pe(e,t){let{isLeaf:n}=e;return!(n===!1&&!Array.isArray(t(e)))}function Fe(e){return e.disabled===!0}function Ie(e,t){return e.isLeaf===!1&&!Array.isArray(t(e))}function Le(e){return e==null?[]:Array.isArray(e)?e:e.checkedKeys??[]}function Re(e){return e==null||Array.isArray(e)?[]:e.indeterminateKeys??[]}function ze(e,t){let n=new Set(e);return t.forEach(e=>{n.has(e)||n.add(e)}),Array.from(n)}function Be(e,t){let n=new Set(e);return t.forEach(e=>{n.has(e)&&n.delete(e)}),Array.from(n)}function Ve(e){return e?.type===`group`}function He(e){let t=new Map;return e.forEach((e,n)=>{t.set(e.key,n)}),e=>t.get(e)??null}var Ue=class extends Error{constructor(){super(),this.message=`SubtreeNotLoadedError: checking a subtree whose required nodes are not fully loaded.`}};function We(e,t,n,r){return Je(t.concat(e),n,r,!1)}function Ge(e,t){let n=new Set;return e.forEach(e=>{let r=t.treeNodeMap.get(e);if(r!==void 0){let e=r.parent;for(;e!==null&&!(e.disabled||n.has(e.key));)n.add(e.key),e=e.parent}}),n}function Ke(e,t,n,r){let i=Je(t,n,r,!1),a=Je(e,n,r,!0),o=Ge(e,n),s=[];return i.forEach(e=>{(a.has(e)||o.has(e))&&s.push(e)}),s.forEach(e=>i.delete(e)),i}function qe(e,t){let{checkedKeys:n,keysToCheck:r,keysToUncheck:i,indeterminateKeys:a,cascade:o,leafOnly:s,checkStrategy:c,allowNotLoaded:l}=e;if(!o)return r===void 0?i===void 0?{checkedKeys:Array.from(n),indeterminateKeys:Array.from(a)}:{checkedKeys:Be(n,i),indeterminateKeys:Array.from(a)}:{checkedKeys:ze(n,r),indeterminateKeys:Array.from(a)};let{levelTreeNodeMap:u}=t,d;d=i===void 0?r===void 0?Je(n,t,l,!1):We(r,n,t,l):Ke(i,n,t,l);let f=c===`parent`,p=c===`child`||s,m=d,h=new Set,g=Math.max.apply(null,Array.from(u.keys()));for(let e=g;e>=0;--e){let t=e===0,n=u.get(e);for(let e of n){if(e.isLeaf)continue;let{key:n,shallowLoaded:r}=e;if(p&&r&&e.children.forEach(e=>{!e.disabled&&!e.isLeaf&&e.shallowLoaded&&m.has(e.key)&&m.delete(e.key)}),e.disabled||!r)continue;let i=!0,a=!1,o=!0;for(let t of e.children){let e=t.key;if(!t.disabled){if(o&&=!1,m.has(e))a=!0;else if(h.has(e)){a=!0,i=!1;break}else if(i=!1,a)break}}i&&!o?(f&&e.children.forEach(e=>{!e.disabled&&m.has(e.key)&&m.delete(e.key)}),m.add(n)):a&&h.add(n),t&&p&&m.has(n)&&m.delete(n)}}return{checkedKeys:Array.from(m),indeterminateKeys:Array.from(h)}}function Je(e,t,n,r){let{treeNodeMap:i,getChildren:a}=t,o=new Set,s=new Set(e);return e.forEach(e=>{let t=i.get(e);t!==void 0&&Oe(t,e=>{if(e.disabled)return De.STOP;let{key:t}=e;if(!o.has(t)&&(o.add(t),s.add(t),Ie(e.rawNode,a))){if(r)return De.STOP;if(!n)throw new Ue}})}),s}function Ye(e,{includeGroup:t=!1,includeSelf:n=!0},r){let i=r.treeNodeMap,a=e==null?null:i.get(e)??null,o={keyPath:[],treeNodePath:[],treeNode:a};if(a?.ignored)return o.treeNode=null,o;for(;a;)!a.ignored&&(t||!a.isGroup)&&o.treeNodePath.push(a),a=a.parent;return o.treeNodePath.reverse(),n||o.treeNodePath.pop(),o.keyPath=o.treeNodePath.map(e=>e.key),o}function Xe(e){if(e.length===0)return null;let t=e[0];return t.isGroup||t.ignored||t.disabled?t.getNext():t}function Ze(e,t){let n=e.siblings,r=n.length,{index:i}=e;return t?n[(i+1)%r]:i===n.length-1?null:n[i+1]}function Qe(e,t,{loop:n=!1,includeDisabled:r=!1}={}){let i=t===`prev`?$e:Ze,a={reverse:t===`prev`},o=!1,s=null;function c(t){if(t!==null){if(t===e){if(!o)o=!0;else if(!e.disabled&&!e.isGroup){s=e;return}}else if((!t.disabled||r)&&!t.ignored&&!t.isGroup){s=t;return}if(t.isGroup){let e=tt(t,a);e===null?c(i(t,n)):s=e}else{let e=i(t,!1);if(e!==null)c(e);else{let e=et(t);e?.isGroup?c(i(e,n)):n&&c(i(t,!0))}}}}return c(e),s}function $e(e,t){let n=e.siblings,r=n.length,{index:i}=e;return t?n[(i-1+r)%r]:i===0?null:n[i-1]}function et(e){return e.parent}function tt(e,t={}){let{reverse:n=!1}=t,{children:r}=e;if(r){let{length:e}=r,i=n?e-1:0,a=n?-1:e,o=n?-1:1;for(let e=i;e!==a;e+=o){let n=r[e];if(!n.disabled&&!n.ignored)if(n.isGroup){let e=tt(n,t);if(e!==null)return e}else return n}}return null}var nt={getChild(){return this.ignored?null:tt(this)},getParent(){let{parent:e}=this;return e?.isGroup?e.getParent():e},getNext(e={}){return Qe(this,`next`,e)},getPrev(e={}){return Qe(this,`prev`,e)}};function rt(e,t){let n=t?new Set(t):void 0,r=[];function i(e){e.forEach(e=>{r.push(e),!(e.isLeaf||!e.children||e.ignored)&&(e.isGroup||n===void 0||n.has(e.key))&&i(e.children)})}return i(e),r}function it(e,t){let n=e.key;for(;t;){if(t.key===n)return!0;t=t.parent}return!1}function at(e,t,n,r,i,a=null,o=0){let s=[];return e.forEach((c,l)=>{var u;let d=Object.create(r);if(d.rawNode=c,d.siblings=s,d.level=o,d.index=l,d.isFirstChild=l===0,d.isLastChild=l+1===e.length,d.parent=a,!d.ignored){let e=i(c);Array.isArray(e)&&(d.children=at(e,t,n,r,i,d,o+1))}s.push(d),t.set(d.key,d),n.has(o)||n.set(o,[]),(u=n.get(o))==null||u.push(d)}),s}function ot(e,t={}){let n=new Map,r=new Map,{getDisabled:i=Fe,getIgnored:a=Ne,getIsGroup:o=Ve,getKey:s=Me}=t,c=t.getChildren??je,l=t.ignoreEmptyChildren?e=>{let t=c(e);return Array.isArray(t)?t.length?t:null:t}:c,u=at(e,n,r,Object.assign({get key(){return s(this.rawNode)},get disabled(){return i(this.rawNode)},get isGroup(){return o(this.rawNode)},get isLeaf(){return Ae(this.rawNode,l)},get shallowLoaded(){return Pe(this.rawNode,l)},get ignored(){return a(this.rawNode)},contains(e){return it(this,e)}},nt),l);function d(e){if(e==null)return null;let t=n.get(e);return t&&!t.isGroup&&!t.ignored?t:null}function f(e){if(e==null)return null;let t=n.get(e);return t&&!t.ignored?t:null}function p(e,t){let n=f(e);return n?n.getPrev(t):null}function m(e,t){let n=f(e);return n?n.getNext(t):null}function h(e){let t=f(e);return t?t.getParent():null}function g(e){let t=f(e);return t?t.getChild():null}let _={treeNodes:u,treeNodeMap:n,levelTreeNodeMap:r,maxLevel:Math.max(...r.keys()),getChildren:l,getFlattenedNodes(e){return rt(u,e)},getNode:d,getPrev:p,getNext:m,getParent:h,getChild:g,getFirstAvailableNode(){return Xe(u)},getPath(e,t={}){return Ye(e,t,_)},getCheckedKeys(e,t={}){let{cascade:n=!0,leafOnly:r=!1,checkStrategy:i=`all`,allowNotLoaded:a=!1}=t;return qe({checkedKeys:Le(e),indeterminateKeys:Re(e),cascade:n,leafOnly:r,checkStrategy:i,allowNotLoaded:a},_)},check(e,t,n={}){let{cascade:r=!0,leafOnly:i=!1,checkStrategy:a=`all`,allowNotLoaded:o=!1}=n;return qe({checkedKeys:Le(t),indeterminateKeys:Re(t),keysToCheck:e==null?[]:Ee(e),cascade:r,leafOnly:i,checkStrategy:a,allowNotLoaded:o},_)},uncheck(e,t,n={}){let{cascade:r=!0,leafOnly:i=!1,checkStrategy:a=`all`,allowNotLoaded:o=!1}=n;return qe({checkedKeys:Le(t),indeterminateKeys:Re(t),keysToUncheck:e==null?[]:Ee(e),cascade:r,leafOnly:i,checkStrategy:a,allowNotLoaded:o},_)},getNonLeafKeys(e={}){return ke(u,e)}};return _}var st=X(`empty`,`
 display: flex;
 flex-direction: column;
 align-items: center;
 font-size: var(--n-font-size);
`,[V(`icon`,`
 width: var(--n-icon-size);
 height: var(--n-icon-size);
 font-size: var(--n-icon-size);
 line-height: var(--n-icon-size);
 color: var(--n-icon-color);
 transition:
 color .3s var(--n-bezier);
 `,[z(`+`,[V(`description`,`
 margin-top: 8px;
 `)])]),V(`description`,`
 transition: color .3s var(--n-bezier);
 color: var(--n-text-color);
 `),V(`extra`,`
 text-align: center;
 transition: color .3s var(--n-bezier);
 margin-top: 12px;
 color: var(--n-extra-text-color);
 `)]),ct=L({name:`Empty`,props:Object.assign(Object.assign({},F.props),{description:String,showDescription:{type:Boolean,default:!0},showIcon:{type:Boolean,default:!0},size:{type:String,default:`medium`},renderIcon:Function}),slots:Object,setup(e){let{mergedClsPrefixRef:t,inlineThemeDisabled:n,mergedComponentPropsRef:r}=O(e),i=F(`Empty`,`-empty`,st,P,e,t),{localeRef:a}=h(`Empty`),o=M(()=>e.description??r?.value?.Empty?.description),s=M(()=>r?.value?.Empty?.renderIcon||(()=>j(Te,null))),c=M(()=>{let{size:t}=e,{common:{cubicBezierEaseInOut:n},self:{[T(`iconSize`,t)]:r,[T(`fontSize`,t)]:a,textColor:o,iconColor:s,extraTextColor:c}}=i.value;return{"--n-icon-size":r,"--n-font-size":a,"--n-bezier":n,"--n-text-color":o,"--n-icon-color":s,"--n-extra-text-color":c}}),l=n?ie(`empty`,M(()=>{let t=``,{size:n}=e;return t+=n[0],t}),c,e):void 0;return{mergedClsPrefix:t,mergedRenderIcon:s,localizedDescription:M(()=>o.value||a.value.description),cssVars:n?void 0:c,themeClass:l?.themeClass,onRender:l?.onRender}},render(){let{$slots:e,mergedClsPrefix:t,onRender:n}=this;return n?.(),j(`div`,{class:[`${t}-empty`,this.themeClass],style:this.cssVars},this.showIcon?j(`div`,{class:`${t}-empty__icon`},e.icon?e.icon():j(R,{clsPrefix:t},{default:this.mergedRenderIcon})):null,this.showDescription?j(`div`,{class:`${t}-empty__description`},e.default?e.default():this.localizedDescription):null,e.extra?j(`div`,{class:`${t}-empty__extra`},e.extra()):null)}}),lt=L({name:`NBaseSelectGroupHeader`,props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(){let{renderLabelRef:e,renderOptionRef:n,labelFieldRef:r,nodePropsRef:i}=q(t);return{labelField:r,nodeProps:i,renderLabel:e,renderOption:n}},render(){let{clsPrefix:e,renderLabel:t,renderOption:n,nodeProps:r,tmNode:{rawNode:i}}=this,a=r?.(i),o=t?t(i,!1):A(i[this.labelField],i,!1),s=j(`div`,Object.assign({},a,{class:[`${e}-base-select-group-header`,a?.class]}),o);return i.render?i.render({node:s,option:i}):n?n({node:s,option:i,selected:!1}):s}});function ut(e,t){return j(E,{name:`fade-in-scale-up-transition`},{default:()=>e?j(R,{clsPrefix:t,class:`${t}-base-select-option__check`},{default:()=>j(we)}):null})}var dt=L({name:`NBaseSelectOption`,props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(e){let{valueRef:n,pendingTmNodeRef:r,multipleRef:i,valueSetRef:a,renderLabelRef:o,renderOptionRef:s,labelFieldRef:c,valueFieldRef:l,showCheckmarkRef:u,nodePropsRef:d,handleOptionClick:f,handleOptionMouseEnter:p}=q(t),m=oe(()=>{let{value:t}=r;return t?e.tmNode.key===t.key:!1});function h(t){let{tmNode:n}=e;n.disabled||f(t,n)}function g(t){let{tmNode:n}=e;n.disabled||p(t,n)}function _(t){let{tmNode:n}=e,{value:r}=m;n.disabled||r||p(t,n)}return{multiple:i,isGrouped:oe(()=>{let{tmNode:t}=e,{parent:n}=t;return n&&n.rawNode.type===`group`}),showCheckmark:u,nodeProps:d,isPending:m,isSelected:oe(()=>{let{value:t}=n,{value:r}=i;if(t===null)return!1;let o=e.tmNode.rawNode[l.value];if(r){let{value:e}=a;return e.has(o)}else return t===o}),labelField:c,renderLabel:o,renderOption:s,handleMouseMove:_,handleMouseEnter:g,handleClick:h}},render(){let{clsPrefix:e,tmNode:{rawNode:t},isSelected:n,isPending:r,isGrouped:i,showCheckmark:a,nodeProps:o,renderOption:s,renderLabel:c,handleClick:l,handleMouseEnter:u,handleMouseMove:d}=this,f=ut(n,e),p=c?[c(t,n),a&&f]:[A(t[this.labelField],t,n),a&&f],m=o?.(t),h=j(`div`,Object.assign({},m,{class:[`${e}-base-select-option`,t.class,m?.class,{[`${e}-base-select-option--disabled`]:t.disabled,[`${e}-base-select-option--selected`]:n,[`${e}-base-select-option--grouped`]:i,[`${e}-base-select-option--pending`]:r,[`${e}-base-select-option--show-checkmark`]:a}],style:[m?.style||``,t.style||``],onClick:Ce([l,m?.onClick]),onMouseenter:Ce([u,m?.onMouseenter]),onMousemove:Ce([d,m?.onMousemove])}),j(`div`,{class:`${e}-base-select-option__content`},p));return t.render?t.render({node:h,option:t,selected:n}):s?s({node:h,option:t,selected:n}):h}}),ft=X(`base-select-menu`,`
 line-height: 1.5;
 outline: none;
 z-index: 0;
 position: relative;
 border-radius: var(--n-border-radius);
 transition:
 background-color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier);
 background-color: var(--n-color);
`,[X(`scrollbar`,`
 max-height: var(--n-height);
 `),X(`virtual-list`,`
 max-height: var(--n-height);
 `),X(`base-select-option`,`
 min-height: var(--n-option-height);
 font-size: var(--n-option-font-size);
 display: flex;
 align-items: center;
 `,[V(`content`,`
 z-index: 1;
 white-space: nowrap;
 text-overflow: ellipsis;
 overflow: hidden;
 `)]),X(`base-select-group-header`,`
 min-height: var(--n-option-height);
 font-size: .93em;
 display: flex;
 align-items: center;
 `),X(`base-select-menu-option-wrapper`,`
 position: relative;
 width: 100%;
 `),V(`loading, empty`,`
 display: flex;
 padding: 12px 32px;
 flex: 1;
 justify-content: center;
 `),V(`loading`,`
 color: var(--n-loading-color);
 font-size: var(--n-loading-size);
 `),V(`header`,`
 padding: 8px var(--n-option-padding-left);
 font-size: var(--n-option-font-size);
 transition: 
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 border-bottom: 1px solid var(--n-action-divider-color);
 color: var(--n-action-text-color);
 `),V(`action`,`
 padding: 8px var(--n-option-padding-left);
 font-size: var(--n-option-font-size);
 transition: 
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 border-top: 1px solid var(--n-action-divider-color);
 color: var(--n-action-text-color);
 `),X(`base-select-group-header`,`
 position: relative;
 cursor: default;
 padding: var(--n-option-padding);
 color: var(--n-group-header-text-color);
 `),X(`base-select-option`,`
 cursor: pointer;
 position: relative;
 padding: var(--n-option-padding);
 transition:
 color .3s var(--n-bezier),
 opacity .3s var(--n-bezier);
 box-sizing: border-box;
 color: var(--n-option-text-color);
 opacity: 1;
 `,[Z(`show-checkmark`,`
 padding-right: calc(var(--n-option-padding-right) + 20px);
 `),z(`&::before`,`
 content: "";
 position: absolute;
 left: 4px;
 right: 4px;
 top: 0;
 bottom: 0;
 border-radius: var(--n-border-radius);
 transition: background-color .3s var(--n-bezier);
 `),z(`&:active`,`
 color: var(--n-option-text-color-pressed);
 `),Z(`grouped`,`
 padding-left: calc(var(--n-option-padding-left) * 1.5);
 `),Z(`pending`,[z(`&::before`,`
 background-color: var(--n-option-color-pending);
 `)]),Z(`selected`,`
 color: var(--n-option-text-color-active);
 `,[z(`&::before`,`
 background-color: var(--n-option-color-active);
 `),Z(`pending`,[z(`&::before`,`
 background-color: var(--n-option-color-active-pending);
 `)])]),Z(`disabled`,`
 cursor: not-allowed;
 `,[I(`selected`,`
 color: var(--n-option-text-color-disabled);
 `),Z(`selected`,`
 opacity: var(--n-option-opacity-disabled);
 `)]),V(`check`,`
 font-size: 16px;
 position: absolute;
 right: calc(var(--n-option-padding-right) - 4px);
 top: calc(50% - 7px);
 color: var(--n-option-check-color);
 transition: color .3s var(--n-bezier);
 `,[v({enterScale:`0.5`})])])]),pt=L({name:`InternalSelectMenu`,props:Object.assign(Object.assign({},F.props),{clsPrefix:{type:String,required:!0},scrollable:{type:Boolean,default:!0},treeMate:{type:Object,required:!0},multiple:Boolean,size:{type:String,default:`medium`},value:{type:[String,Number,Array],default:null},autoPending:Boolean,virtualScroll:{type:Boolean,default:!0},show:{type:Boolean,default:!0},labelField:{type:String,default:`label`},valueField:{type:String,default:`value`},loading:Boolean,focusable:Boolean,renderLabel:Function,renderOption:Function,nodeProps:Function,showCheckmark:{type:Boolean,default:!0},onMousedown:Function,onScroll:Function,onFocus:Function,onBlur:Function,onKeyup:Function,onKeydown:Function,onTabOut:Function,onMouseenter:Function,onMouseleave:Function,onResize:Function,resetMenuOnOptionsChange:{type:Boolean,default:!0},inlineThemeDisabled:Boolean,scrollbarProps:Object,onToggle:Function}),setup(e){let{mergedClsPrefixRef:r,mergedRtlRef:i,mergedComponentPropsRef:a}=O(e),o=ge(`InternalSelectMenu`,i,r),s=F(`InternalSelectMenu`,`-internal-select-menu`,ft,ne,e,Q(e,`clsPrefix`)),c=W(null),l=W(null),u=W(null),d=M(()=>e.treeMate.getFlattenedNodes()),f=M(()=>He(d.value)),p=W(null);function m(){let{treeMate:t}=e,n=null,{value:r}=e;r===null?n=t.getFirstAvailableNode():(n=e.multiple?t.getNode((r||[])[(r||[]).length-1]):t.getNode(r),(!n||n.disabled)&&(n=t.getFirstAvailableNode())),L(n||null)}function h(){let{value:t}=p;t&&!e.treeMate.getNode(t.key)&&(p.value=null)}let g;_e(()=>e.show,t=>{t?g=_e(()=>e.treeMate,()=>{e.resetMenuOnOptionsChange?(e.autoPending?m():h(),ae(R)):h()},{immediate:!0}):g?.()},{immediate:!0}),w(()=>{g?.()});let _=M(()=>U(s.value.self[T(`optionHeight`,e.size)])),v=M(()=>K(s.value.self[T(`padding`,e.size)])),y=M(()=>e.multiple&&Array.isArray(e.value)?new Set(e.value):new Set),b=M(()=>{let e=d.value;return e&&e.length===0}),S=M(()=>a?.value?.Select?.renderEmpty);function C(t){let{onToggle:n}=e;n&&n(t)}function ee(t){let{onScroll:n}=e;n&&n(t)}function E(e){var t;(t=u.value)==null||t.sync(),ee(e)}function D(){var e;(e=u.value)==null||e.sync()}function k(){let{value:e}=p;return e||null}function A(e,t){t.disabled||L(t,!1)}function j(e,t){t.disabled||C(t)}function te(t){var n;x(t,`action`)||(n=e.onKeyup)==null||n.call(e,t)}function N(t){var n;x(t,`action`)||(n=e.onKeydown)==null||n.call(e,t)}function P(t){var n;(n=e.onMousedown)==null||n.call(e,t),!e.focusable&&t.preventDefault()}function I(){let{value:e}=p;e&&L(e.getNext({loop:!0}),!0)}function re(){let{value:e}=p;e&&L(e.getPrev({loop:!0}),!0)}function L(e,t=!1){p.value=e,t&&R()}function R(){var t,n;let r=p.value;if(!r)return;let i=f.value(r.key);i!==null&&(e.virtualScroll?(t=l.value)==null||t.scrollTo({index:i}):(n=u.value)==null||n.scrollTo({index:i,elSize:_.value}))}function z(t){var n;c.value?.contains(t.target)&&((n=e.onFocus)==null||n.call(e,t))}function oe(t){var n;c.value?.contains(t.relatedTarget)||(n=e.onBlur)==null||n.call(e,t)}B(t,{handleOptionMouseEnter:A,handleOptionClick:j,valueSetRef:y,pendingTmNodeRef:p,nodePropsRef:Q(e,`nodeProps`),showCheckmarkRef:Q(e,`showCheckmark`),multipleRef:Q(e,`multiple`),valueRef:Q(e,`value`),renderLabelRef:Q(e,`renderLabel`),renderOptionRef:Q(e,`renderOption`),labelFieldRef:Q(e,`labelField`),valueFieldRef:Q(e,`valueField`)}),B(n,c),he(()=>{let{value:e}=u;e&&e.sync()});let V=M(()=>{let{size:t}=e,{common:{cubicBezierEaseInOut:n},self:{height:r,borderRadius:i,color:a,groupHeaderTextColor:o,actionDividerColor:c,optionTextColorPressed:l,optionTextColor:u,optionTextColorDisabled:d,optionTextColorActive:f,optionOpacityDisabled:p,optionCheckColor:m,actionTextColor:h,optionColorPending:g,optionColorActive:_,loadingColor:v,loadingSize:y,optionColorActivePending:b,[T(`optionFontSize`,t)]:x,[T(`optionHeight`,t)]:S,[T(`optionPadding`,t)]:C}}=s.value;return{"--n-height":r,"--n-action-divider-color":c,"--n-action-text-color":h,"--n-bezier":n,"--n-border-radius":i,"--n-color":a,"--n-option-font-size":x,"--n-group-header-text-color":o,"--n-option-check-color":m,"--n-option-color-pending":g,"--n-option-color-active":_,"--n-option-color-active-pending":b,"--n-option-height":S,"--n-option-opacity-disabled":p,"--n-option-text-color":u,"--n-option-text-color-active":f,"--n-option-text-color-disabled":d,"--n-option-text-color-pressed":l,"--n-option-padding":C,"--n-option-padding-left":K(C,`left`),"--n-option-padding-right":K(C,`right`),"--n-loading-color":v,"--n-loading-size":y}}),{inlineThemeDisabled:H}=e,se=H?ie(`internal-select-menu`,M(()=>e.size[0]),V,e):void 0,ce={selfRef:c,next:I,prev:re,getPendingTmNode:k};return xe(c,e.onResize),Object.assign({mergedTheme:s,mergedClsPrefix:r,rtlEnabled:o,virtualListRef:l,scrollbarRef:u,itemSize:_,padding:v,flattenedNodes:d,empty:b,mergedRenderEmpty:S,virtualListContainer(){let{value:e}=l;return e?.listElRef},virtualListContent(){let{value:e}=l;return e?.itemsElRef},doScroll:ee,handleFocusin:z,handleFocusout:oe,handleKeyUp:te,handleKeyDown:N,handleMouseDown:P,handleVirtualListResize:D,handleVirtualListScroll:E,cssVars:H?void 0:V,themeClass:se?.themeClass,onRender:se?.onRender},ce)},render(){let{$slots:e,virtualScroll:t,clsPrefix:n,mergedTheme:r,themeClass:a,onRender:o}=this;return o?.(),j(`div`,{ref:`selfRef`,tabindex:this.focusable?0:-1,class:[`${n}-base-select-menu`,`${n}-base-select-menu--${this.size}-size`,this.rtlEnabled&&`${n}-base-select-menu--rtl`,a,this.multiple&&`${n}-base-select-menu--multiple`],style:this.cssVars,onFocusin:this.handleFocusin,onFocusout:this.handleFocusout,onKeyup:this.handleKeyUp,onKeydown:this.handleKeyDown,onMousedown:this.handleMouseDown,onMouseenter:this.onMouseenter,onMouseleave:this.onMouseleave},i(e.header,e=>e&&j(`div`,{class:`${n}-base-select-menu__header`,"data-header":!0,key:`header`},e)),this.loading?j(`div`,{class:`${n}-base-select-menu__loading`},j(ve,{clsPrefix:n,strokeWidth:20})):this.empty?j(`div`,{class:`${n}-base-select-menu__empty`,"data-empty":!0},l(e.empty,()=>[this.mergedRenderEmpty?.call(this)||j(ct,{theme:r.peers.Empty,themeOverrides:r.peerOverrides.Empty,size:this.size})])):j(D,Object.assign({ref:`scrollbarRef`,theme:r.peers.Scrollbar,themeOverrides:r.peerOverrides.Scrollbar,scrollable:this.scrollable,container:t?this.virtualListContainer:void 0,content:t?this.virtualListContent:void 0,onScroll:t?void 0:this.doScroll},this.scrollbarProps),{default:()=>t?j(_,{ref:`virtualListRef`,class:`${n}-virtual-list`,items:this.flattenedNodes,itemSize:this.itemSize,showScrollbar:!1,paddingTop:this.padding.top,paddingBottom:this.padding.bottom,onResize:this.handleVirtualListResize,onScroll:this.handleVirtualListScroll,itemResizable:!0},{default:({item:e})=>e.isGroup?j(lt,{key:e.key,clsPrefix:n,tmNode:e}):e.ignored?null:j(dt,{clsPrefix:n,key:e.key,tmNode:e})}):j(`div`,{class:`${n}-base-select-menu-option-wrapper`,style:{paddingTop:this.padding.top,paddingBottom:this.padding.bottom}},this.flattenedNodes.map(e=>e.isGroup?j(lt,{key:e.key,clsPrefix:n,tmNode:e}):j(dt,{clsPrefix:n,key:e.key,tmNode:e})))}),i(e.action,e=>e&&[j(`div`,{class:`${n}-base-select-menu__action`,"data-action":!0,key:`action`},e),j(y,{onFocus:this.onTabOut,key:`focus-detector`})]))}});function mt(e){let{textColor2:t,primaryColorHover:n,primaryColorPressed:r,primaryColor:i,infoColor:a,successColor:o,warningColor:s,errorColor:c,baseColor:l,borderColor:u,opacityDisabled:d,tagColor:f,closeIconColor:p,closeIconColorHover:m,closeIconColorPressed:h,borderRadiusSmall:g,fontSizeMini:_,fontSizeTiny:v,fontSizeSmall:y,fontSizeMedium:b,heightMini:x,heightTiny:S,heightSmall:C,heightMedium:w,closeColorHover:ee,closeColorPressed:T,buttonColor2Hover:E,buttonColor2Pressed:D,fontWeightStrong:O}=e;return Object.assign(Object.assign({},le),{closeBorderRadius:g,heightTiny:x,heightSmall:S,heightMedium:C,heightLarge:w,borderRadius:g,opacityDisabled:d,fontSizeTiny:_,fontSizeSmall:v,fontSizeMedium:y,fontSizeLarge:b,fontWeightStrong:O,textColorCheckable:t,textColorHoverCheckable:t,textColorPressedCheckable:t,textColorChecked:l,colorCheckable:`#0000`,colorHoverCheckable:E,colorPressedCheckable:D,colorChecked:i,colorCheckedHover:n,colorCheckedPressed:r,border:`1px solid ${u}`,textColor:t,color:f,colorBordered:`rgb(250, 250, 252)`,closeIconColor:p,closeIconColorHover:m,closeIconColorPressed:h,closeColorHover:ee,closeColorPressed:T,borderPrimary:`1px solid ${G(i,{alpha:.3})}`,textColorPrimary:i,colorPrimary:G(i,{alpha:.12}),colorBorderedPrimary:G(i,{alpha:.1}),closeIconColorPrimary:i,closeIconColorHoverPrimary:i,closeIconColorPressedPrimary:i,closeColorHoverPrimary:G(i,{alpha:.12}),closeColorPressedPrimary:G(i,{alpha:.18}),borderInfo:`1px solid ${G(a,{alpha:.3})}`,textColorInfo:a,colorInfo:G(a,{alpha:.12}),colorBorderedInfo:G(a,{alpha:.1}),closeIconColorInfo:a,closeIconColorHoverInfo:a,closeIconColorPressedInfo:a,closeColorHoverInfo:G(a,{alpha:.12}),closeColorPressedInfo:G(a,{alpha:.18}),borderSuccess:`1px solid ${G(o,{alpha:.3})}`,textColorSuccess:o,colorSuccess:G(o,{alpha:.12}),colorBorderedSuccess:G(o,{alpha:.1}),closeIconColorSuccess:o,closeIconColorHoverSuccess:o,closeIconColorPressedSuccess:o,closeColorHoverSuccess:G(o,{alpha:.12}),closeColorPressedSuccess:G(o,{alpha:.18}),borderWarning:`1px solid ${G(s,{alpha:.35})}`,textColorWarning:s,colorWarning:G(s,{alpha:.15}),colorBorderedWarning:G(s,{alpha:.12}),closeIconColorWarning:s,closeIconColorHoverWarning:s,closeIconColorPressedWarning:s,closeColorHoverWarning:G(s,{alpha:.12}),closeColorPressedWarning:G(s,{alpha:.18}),borderError:`1px solid ${G(c,{alpha:.23})}`,textColorError:c,colorError:G(c,{alpha:.1}),colorBorderedError:G(c,{alpha:.08}),closeIconColorError:c,closeIconColorHoverError:c,closeIconColorPressedError:c,closeColorHoverError:G(c,{alpha:.12}),closeColorPressedError:G(c,{alpha:.18})})}var ht={name:`Tag`,common:te,self:mt},gt={color:Object,type:{type:String,default:`default`},round:Boolean,size:String,closable:Boolean,disabled:{type:Boolean,default:void 0}},_t=X(`tag`,`
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
`,[Z(`strong`,`
 font-weight: var(--n-font-weight-strong);
 `),V(`border`,`
 pointer-events: none;
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 border-radius: inherit;
 border: var(--n-border);
 transition: border-color .3s var(--n-bezier);
 `),V(`icon`,`
 display: flex;
 margin: 0 4px 0 0;
 color: var(--n-text-color);
 transition: color .3s var(--n-bezier);
 font-size: var(--n-avatar-size-override);
 `),V(`avatar`,`
 display: flex;
 margin: 0 6px 0 0;
 `),V(`close`,`
 margin: var(--n-close-margin);
 transition:
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 `),Z(`round`,`
 padding: 0 calc(var(--n-height) / 3);
 border-radius: calc(var(--n-height) / 2);
 `,[V(`icon`,`
 margin: 0 4px 0 calc((var(--n-height) - 8px) / -2);
 `),V(`avatar`,`
 margin: 0 6px 0 calc((var(--n-height) - 8px) / -2);
 `),Z(`closable`,`
 padding: 0 calc(var(--n-height) / 4) 0 calc(var(--n-height) / 3);
 `)]),Z(`icon, avatar`,[Z(`round`,`
 padding: 0 calc(var(--n-height) / 3) 0 calc(var(--n-height) / 2);
 `)]),Z(`disabled`,`
 cursor: not-allowed !important;
 opacity: var(--n-opacity-disabled);
 `),Z(`checkable`,`
 cursor: pointer;
 box-shadow: none;
 color: var(--n-text-color-checkable);
 background-color: var(--n-color-checkable);
 `,[I(`disabled`,[z(`&:hover`,`background-color: var(--n-color-hover-checkable);`,[I(`checked`,`color: var(--n-text-color-hover-checkable);`)]),z(`&:active`,`background-color: var(--n-color-pressed-checkable);`,[I(`checked`,`color: var(--n-text-color-pressed-checkable);`)])]),Z(`checked`,`
 color: var(--n-text-color-checked);
 background-color: var(--n-color-checked);
 `,[I(`disabled`,[z(`&:hover`,`background-color: var(--n-color-checked-hover);`),z(`&:active`,`background-color: var(--n-color-checked-pressed);`)])])])]),vt=Object.assign(Object.assign(Object.assign({},F.props),gt),{bordered:{type:Boolean,default:void 0},checked:Boolean,checkable:Boolean,strong:Boolean,triggerClickOnClose:Boolean,onClose:[Array,Function],onMouseenter:Function,onMouseleave:Function,"onUpdate:checked":Function,onUpdateChecked:Function,internalCloseFocusable:{type:Boolean,default:!0},internalCloseIsButtonTag:{type:Boolean,default:!0},onCheckedChange:Function}),yt=pe(`n-tag`),bt=L({name:`Tag`,props:vt,slots:Object,setup(e){let t=W(null),{mergedBorderedRef:n,mergedClsPrefixRef:r,inlineThemeDisabled:i,mergedRtlRef:a,mergedComponentPropsRef:o}=O(e),c=M(()=>e.size||o?.value?.Tag?.size||`medium`),l=F(`Tag`,`-tag`,_t,ht,e,r);B(yt,{roundRef:Q(e,`round`)});function u(){if(!e.disabled&&e.checkable){let{checked:t,onCheckedChange:n,onUpdateChecked:r,"onUpdate:checked":i}=e;r&&r(!t),i&&i(!t),n&&n(!t)}}function d(t){if(e.triggerClickOnClose||t.stopPropagation(),!e.disabled){let{onClose:n}=e;n&&s(n,t)}}let p={setTextContent(e){let{value:n}=t;n&&(n.textContent=e)}},m=ge(`Tag`,a,r),h=M(()=>{let{type:t,color:{color:r,textColor:i}={}}=e,a=c.value,{common:{cubicBezierEaseInOut:o},self:{padding:s,closeMargin:u,borderRadius:d,opacityDisabled:f,textColorCheckable:p,textColorHoverCheckable:m,textColorPressedCheckable:h,textColorChecked:g,colorCheckable:_,colorHoverCheckable:v,colorPressedCheckable:y,colorChecked:b,colorCheckedHover:x,colorCheckedPressed:S,closeBorderRadius:C,fontWeightStrong:w,[T(`colorBordered`,t)]:ee,[T(`closeSize`,a)]:E,[T(`closeIconSize`,a)]:D,[T(`fontSize`,a)]:O,[T(`height`,a)]:k,[T(`color`,t)]:A,[T(`textColor`,t)]:j,[T(`border`,t)]:te,[T(`closeIconColor`,t)]:M,[T(`closeIconColorHover`,t)]:ne,[T(`closeIconColorPressed`,t)]:N,[T(`closeColorHover`,t)]:P,[T(`closeColorPressed`,t)]:F}}=l.value,I=K(u);return{"--n-font-weight-strong":w,"--n-avatar-size-override":`calc(${k} - 8px)`,"--n-bezier":o,"--n-border-radius":d,"--n-border":te,"--n-close-icon-size":D,"--n-close-color-pressed":F,"--n-close-color-hover":P,"--n-close-border-radius":C,"--n-close-icon-color":M,"--n-close-icon-color-hover":ne,"--n-close-icon-color-pressed":N,"--n-close-icon-color-disabled":M,"--n-close-margin-top":I.top,"--n-close-margin-right":I.right,"--n-close-margin-bottom":I.bottom,"--n-close-margin-left":I.left,"--n-close-size":E,"--n-color":r||(n.value?ee:A),"--n-color-checkable":_,"--n-color-checked":b,"--n-color-checked-hover":x,"--n-color-checked-pressed":S,"--n-color-hover-checkable":v,"--n-color-pressed-checkable":y,"--n-font-size":O,"--n-height":k,"--n-opacity-disabled":f,"--n-padding":s,"--n-text-color":i||j,"--n-text-color-checkable":p,"--n-text-color-checked":g,"--n-text-color-hover-checkable":m,"--n-text-color-pressed-checkable":h}}),g=i?ie(`tag`,M(()=>{let t=``,{type:r,color:{color:i,textColor:a}={}}=e;return t+=r[0],t+=c.value[0],i&&(t+=`a${f(i)}`),a&&(t+=`b${f(a)}`),n.value&&(t+=`c`),t}),h,e):void 0;return Object.assign(Object.assign({},p),{rtlEnabled:m,mergedClsPrefix:r,contentRef:t,mergedBordered:n,handleClick:u,handleCloseClick:d,cssVars:i?void 0:h,themeClass:g?.themeClass,onRender:g?.onRender})},render(){var e;let{mergedClsPrefix:t,rtlEnabled:n,closable:r,color:{borderColor:a}={},round:o,onRender:s,$slots:c}=this;s?.();let l=i(c.avatar,e=>e&&j(`div`,{class:`${t}-tag__avatar`},e)),u=i(c.icon,e=>e&&j(`div`,{class:`${t}-tag__icon`},e));return j(`div`,{class:[`${t}-tag`,this.themeClass,{[`${t}-tag--rtl`]:n,[`${t}-tag--strong`]:this.strong,[`${t}-tag--disabled`]:this.disabled,[`${t}-tag--checkable`]:this.checkable,[`${t}-tag--checked`]:this.checkable&&this.checked,[`${t}-tag--round`]:o,[`${t}-tag--avatar`]:l,[`${t}-tag--icon`]:u,[`${t}-tag--closable`]:r}],style:this.cssVars,onClick:this.handleClick,onMouseenter:this.onMouseenter,onMouseleave:this.onMouseleave},u||l,j(`span`,{class:`${t}-tag__content`,ref:`contentRef`},(e=this.$slots).default?.call(e)),!this.checkable&&r?j(k,{clsPrefix:t,class:`${t}-tag__close`,disabled:this.disabled,onClick:this.handleCloseClick,focusable:this.internalCloseFocusable,round:o,isButtonTag:this.internalCloseIsButtonTag,absolute:!0}):null,!this.checkable&&this.mergedBordered?j(`div`,{class:`${t}-tag__border`,style:{borderColor:a}}):null)}}),xt=z([X(`base-selection`,`
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
 `,[X(`base-loading`,`
 color: var(--n-loading-color);
 `),X(`base-selection-tags`,`min-height: var(--n-height);`),V(`border, state-border`,`
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
 `),V(`state-border`,`
 z-index: 1;
 border-color: #0000;
 `),X(`base-suffix`,`
 cursor: pointer;
 position: absolute;
 top: 50%;
 transform: translateY(-50%);
 right: 10px;
 `,[V(`arrow`,`
 font-size: var(--n-arrow-size);
 color: var(--n-arrow-color);
 transition: color .3s var(--n-bezier);
 `)]),X(`base-selection-overlay`,`
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
 `,[V(`wrapper`,`
 flex-basis: 0;
 flex-grow: 1;
 overflow: hidden;
 text-overflow: ellipsis;
 `)]),X(`base-selection-placeholder`,`
 color: var(--n-placeholder-color);
 `,[V(`inner`,`
 max-width: 100%;
 overflow: hidden;
 `)]),X(`base-selection-tags`,`
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
 `),X(`base-selection-label`,`
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
 `,[X(`base-selection-input`,`
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
 `,[V(`content`,`
 text-overflow: ellipsis;
 overflow: hidden;
 white-space: nowrap; 
 `)]),V(`render-label`,`
 color: var(--n-text-color);
 `)]),I(`disabled`,[z(`&:hover`,[V(`state-border`,`
 box-shadow: var(--n-box-shadow-hover);
 border: var(--n-border-hover);
 `)]),Z(`focus`,[V(`state-border`,`
 box-shadow: var(--n-box-shadow-focus);
 border: var(--n-border-focus);
 `)]),Z(`active`,[V(`state-border`,`
 box-shadow: var(--n-box-shadow-active);
 border: var(--n-border-active);
 `),X(`base-selection-label`,`background-color: var(--n-color-active);`),X(`base-selection-tags`,`background-color: var(--n-color-active);`)])]),Z(`disabled`,`cursor: not-allowed;`,[V(`arrow`,`
 color: var(--n-arrow-color-disabled);
 `),X(`base-selection-label`,`
 cursor: not-allowed;
 background-color: var(--n-color-disabled);
 `,[X(`base-selection-input`,`
 cursor: not-allowed;
 color: var(--n-text-color-disabled);
 `),V(`render-label`,`
 color: var(--n-text-color-disabled);
 `)]),X(`base-selection-tags`,`
 cursor: not-allowed;
 background-color: var(--n-color-disabled);
 `),X(`base-selection-placeholder`,`
 cursor: not-allowed;
 color: var(--n-placeholder-color-disabled);
 `)]),X(`base-selection-input-tag`,`
 height: calc(var(--n-height) - 6px);
 line-height: calc(var(--n-height) - 6px);
 outline: none;
 display: none;
 position: relative;
 margin-bottom: 3px;
 max-width: 100%;
 vertical-align: bottom;
 `,[V(`input`,`
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
 `),V(`mirror`,`
 position: absolute;
 left: 0;
 top: 0;
 white-space: pre;
 visibility: hidden;
 user-select: none;
 -webkit-user-select: none;
 opacity: 0;
 `)]),[`warning`,`error`].map(e=>Z(`${e}-status`,[V(`state-border`,`border: var(--n-border-${e});`),I(`disabled`,[z(`&:hover`,[V(`state-border`,`
 box-shadow: var(--n-box-shadow-hover-${e});
 border: var(--n-border-hover-${e});
 `)]),Z(`active`,[V(`state-border`,`
 box-shadow: var(--n-box-shadow-active-${e});
 border: var(--n-border-active-${e});
 `),X(`base-selection-label`,`background-color: var(--n-color-active-${e});`),X(`base-selection-tags`,`background-color: var(--n-color-active-${e});`)]),Z(`focus`,[V(`state-border`,`
 box-shadow: var(--n-box-shadow-focus-${e});
 border: var(--n-border-focus-${e});
 `)])])]))]),X(`base-selection-popover`,`
 margin-bottom: -3px;
 display: flex;
 flex-wrap: wrap;
 margin-right: -8px;
 `),X(`base-selection-tag-wrapper`,`
 max-width: 100%;
 display: inline-flex;
 padding: 0 7px 3px 0;
 `,[z(`&:last-child`,`padding-right: 0;`),X(`tag`,`
 font-size: 14px;
 max-width: 100%;
 `,[V(`content`,`
 line-height: 1.25;
 text-overflow: ellipsis;
 overflow: hidden;
 `)])])]),St=L({name:`InternalSelection`,props:Object.assign(Object.assign({},F.props),{clsPrefix:{type:String,required:!0},bordered:{type:Boolean,default:void 0},active:Boolean,pattern:{type:String,default:``},placeholder:String,selectedOption:{type:Object,default:null},selectedOptions:{type:Array,default:null},labelField:{type:String,default:`label`},valueField:{type:String,default:`value`},multiple:Boolean,filterable:Boolean,clearable:Boolean,disabled:Boolean,size:{type:String,default:`medium`},loading:Boolean,autofocus:Boolean,showArrow:{type:Boolean,default:!0},inputProps:Object,focused:Boolean,renderTag:Function,onKeydown:Function,onClick:Function,onBlur:Function,onFocus:Function,onDeleteOption:Function,maxTagCount:[String,Number],ellipsisTagPopoverProps:Object,onClear:Function,onPatternInput:Function,onPatternFocus:Function,onPatternBlur:Function,renderLabel:Function,status:String,inlineThemeDisabled:Boolean,ignoreComposition:{type:Boolean,default:!0},onResize:Function}),setup(e){let{mergedClsPrefixRef:t,mergedRtlRef:n}=O(e),r=ge(`InternalSelection`,n,t),i=W(null),a=W(null),o=W(null),s=W(null),c=W(null),l=W(null),u=W(null),d=W(null),f=W(null),p=W(null),m=W(!1),h=W(!1),g=W(!1),_=F(`InternalSelection`,`-internal-selection`,xt,ee,e,Q(e,`clsPrefix`)),v=M(()=>e.clearable&&!e.disabled&&(g.value||e.active)),y=M(()=>e.selectedOption?e.renderTag?e.renderTag({option:e.selectedOption,handleClose:()=>{}}):e.renderLabel?e.renderLabel(e.selectedOption,!0):A(e.selectedOption[e.labelField],e.selectedOption,!0):e.placeholder),b=M(()=>{let t=e.selectedOption;if(t)return t[e.labelField]}),x=M(()=>e.multiple?!!(Array.isArray(e.selectedOptions)&&e.selectedOptions.length):e.selectedOption!==null);function S(){var t;let{value:n}=i;if(n){let{value:r}=a;r&&(r.style.width=`${n.offsetWidth}px`,e.maxTagCount!==`responsive`&&((t=f.value)==null||t.sync({showAllItemsBeforeCalculate:!1})))}}function C(){let{value:e}=p;e&&(e.style.display=`none`)}function w(){let{value:e}=p;e&&(e.style.display=`inline-block`)}_e(Q(e,`active`),e=>{e||C()}),_e(Q(e,`pattern`),()=>{e.multiple&&ae(S)});function E(t){let{onFocus:n}=e;n&&n(t)}function D(t){let{onBlur:n}=e;n&&n(t)}function k(t){let{onDeleteOption:n}=e;n&&n(t)}function j(t){let{onClear:n}=e;n&&n(t)}function te(t){let{onPatternInput:n}=e;n&&n(t)}function ne(e){(!e.relatedTarget||!o.value?.contains(e.relatedTarget))&&E(e)}function N(e){o.value?.contains(e.relatedTarget)||D(e)}function P(e){j(e)}function I(){g.value=!0}function re(){g.value=!1}function L(t){!e.active||!e.filterable||t.target!==a.value&&t.preventDefault()}function R(e){k(e)}let z=W(!1);function oe(t){if(t.key===`Backspace`&&!z.value&&!e.pattern.length){let{selectedOptions:t}=e;t?.length&&R(t[t.length-1])}}let B=null;function V(t){let{value:n}=i;n&&(n.textContent=t.target.value,S()),e.ignoreComposition&&z.value?B=t:te(t)}function U(){z.value=!0}function se(){z.value=!1,e.ignoreComposition&&te(B),B=null}function ce(t){var n;h.value=!0,(n=e.onPatternFocus)==null||n.call(e,t)}function le(t){var n;h.value=!1,(n=e.onPatternBlur)==null||n.call(e,t)}function ue(){var t,n;if(e.filterable)h.value=!1,(t=l.value)==null||t.blur(),(n=a.value)==null||n.blur();else if(e.multiple){let{value:e}=s;e?.blur()}else{let{value:e}=c;e?.blur()}}function G(){var t,n,r;e.filterable?(h.value=!1,(t=l.value)==null||t.focus()):e.multiple?(n=s.value)==null||n.focus():(r=c.value)==null||r.focus()}function de(){let{value:e}=a;e&&(w(),e.focus())}function fe(){let{value:e}=a;e&&e.blur()}function q(e){let{value:t}=u;t&&t.setTextContent(`+${e}`)}function J(){let{value:e}=d;return e}function pe(){return a.value}let Y=null;function me(){Y!==null&&window.clearTimeout(Y)}function X(){e.active||(me(),Y=window.setTimeout(()=>{x.value&&(m.value=!0)},100))}function Z(){me()}function ve(e){e||(me(),m.value=!1)}_e(x,e=>{e||(m.value=!1)}),he(()=>{H(()=>{let t=l.value;t&&(e.disabled?t.removeAttribute(`tabindex`):t.tabIndex=h.value?-1:0)})}),xe(o,e.onResize);let{inlineThemeDisabled:$}=e,ye=M(()=>{let{size:t}=e,{common:{cubicBezierEaseInOut:n},self:{fontWeight:r,borderRadius:i,color:a,placeholderColor:o,textColor:s,paddingSingle:c,paddingMultiple:l,caretColor:u,colorDisabled:d,textColorDisabled:f,placeholderColorDisabled:p,colorActive:m,boxShadowFocus:h,boxShadowActive:g,boxShadowHover:v,border:y,borderFocus:b,borderHover:x,borderActive:S,arrowColor:C,arrowColorDisabled:w,loadingColor:ee,colorActiveWarning:E,boxShadowFocusWarning:D,boxShadowActiveWarning:O,boxShadowHoverWarning:k,borderWarning:A,borderFocusWarning:j,borderHoverWarning:te,borderActiveWarning:M,colorActiveError:ne,boxShadowFocusError:N,boxShadowActiveError:P,boxShadowHoverError:F,borderError:I,borderFocusError:re,borderHoverError:L,borderActiveError:ie,clearColor:R,clearColorHover:ae,clearColorPressed:z,clearSize:oe,arrowSize:B,[T(`height`,t)]:V,[T(`fontSize`,t)]:H}}=_.value,U=K(c),W=K(l);return{"--n-bezier":n,"--n-border":y,"--n-border-active":S,"--n-border-focus":b,"--n-border-hover":x,"--n-border-radius":i,"--n-box-shadow-active":g,"--n-box-shadow-focus":h,"--n-box-shadow-hover":v,"--n-caret-color":u,"--n-color":a,"--n-color-active":m,"--n-color-disabled":d,"--n-font-size":H,"--n-height":V,"--n-padding-single-top":U.top,"--n-padding-multiple-top":W.top,"--n-padding-single-right":U.right,"--n-padding-multiple-right":W.right,"--n-padding-single-left":U.left,"--n-padding-multiple-left":W.left,"--n-padding-single-bottom":U.bottom,"--n-padding-multiple-bottom":W.bottom,"--n-placeholder-color":o,"--n-placeholder-color-disabled":p,"--n-text-color":s,"--n-text-color-disabled":f,"--n-arrow-color":C,"--n-arrow-color-disabled":w,"--n-loading-color":ee,"--n-color-active-warning":E,"--n-box-shadow-focus-warning":D,"--n-box-shadow-active-warning":O,"--n-box-shadow-hover-warning":k,"--n-border-warning":A,"--n-border-focus-warning":j,"--n-border-hover-warning":te,"--n-border-active-warning":M,"--n-color-active-error":ne,"--n-box-shadow-focus-error":N,"--n-box-shadow-active-error":P,"--n-box-shadow-hover-error":F,"--n-border-error":I,"--n-border-focus-error":re,"--n-border-hover-error":L,"--n-border-active-error":ie,"--n-clear-size":oe,"--n-clear-color":R,"--n-clear-color-hover":ae,"--n-clear-color-pressed":z,"--n-arrow-size":B,"--n-font-weight":r}}),be=$?ie(`internal-selection`,M(()=>e.size[0]),ye,e):void 0;return{mergedTheme:_,mergedClearable:v,mergedClsPrefix:t,rtlEnabled:r,patternInputFocused:h,filterablePlaceholder:y,label:b,selected:x,showTagsPanel:m,isComposing:z,counterRef:u,counterWrapperRef:d,patternInputMirrorRef:i,patternInputRef:a,selfRef:o,multipleElRef:s,singleElRef:c,patternInputWrapperRef:l,overflowRef:f,inputTagElRef:p,handleMouseDown:L,handleFocusin:ne,handleClear:P,handleMouseEnter:I,handleMouseLeave:re,handleDeleteOption:R,handlePatternKeyDown:oe,handlePatternInputInput:V,handlePatternInputBlur:le,handlePatternInputFocus:ce,handleMouseEnterCounter:X,handleMouseLeaveCounter:Z,handleFocusout:N,handleCompositionEnd:se,handleCompositionStart:U,onPopoverUpdateShow:ve,focus:G,focusInput:de,blur:ue,blurInput:fe,updateCounter:q,getCounter:J,getTail:pe,renderLabel:e.renderLabel,cssVars:$?void 0:ye,themeClass:be?.themeClass,onRender:be?.onRender}},render(){let{status:e,multiple:t,size:n,disabled:r,filterable:i,maxTagCount:a,bordered:o,clsPrefix:s,ellipsisTagPopoverProps:c,onRender:l,renderTag:u,renderLabel:d}=this;l?.();let f=a===`responsive`,p=typeof a==`number`,m=f||p,h=j(J,null,{default:()=>j(b,{clsPrefix:s,loading:this.loading,showArrow:this.showArrow,showClear:this.mergedClearable&&this.selected,onClear:this.handleClear},{default:()=>{var e;return(e=this.$slots).arrow?.call(e)}})}),g;if(t){let{labelField:e}=this,t=t=>j(`div`,{class:`${s}-base-selection-tag-wrapper`,key:t.value},u?u({option:t,handleClose:()=>{this.handleDeleteOption(t)}}):j(bt,{size:n,closable:!t.disabled,disabled:r,onClose:()=>{this.handleDeleteOption(t)},internalCloseIsButtonTag:!1,internalCloseFocusable:!1},{default:()=>d?d(t,!0):A(t[e],t,!0)})),o=()=>(p?this.selectedOptions.slice(0,a):this.selectedOptions).map(t),l=i?j(`div`,{class:`${s}-base-selection-input-tag`,ref:`inputTagElRef`,key:`__input-tag__`},j(`input`,Object.assign({},this.inputProps,{ref:`patternInputRef`,tabindex:-1,disabled:r,value:this.pattern,autofocus:this.autofocus,class:`${s}-base-selection-input-tag__input`,onBlur:this.handlePatternInputBlur,onFocus:this.handlePatternInputFocus,onKeydown:this.handlePatternKeyDown,onInput:this.handlePatternInputInput,onCompositionstart:this.handleCompositionStart,onCompositionend:this.handleCompositionEnd})),j(`span`,{ref:`patternInputMirrorRef`,class:`${s}-base-selection-input-tag__mirror`},this.pattern)):null,_=f?()=>j(`div`,{class:`${s}-base-selection-tag-wrapper`,ref:`counterWrapperRef`},j(bt,{size:n,ref:`counterRef`,onMouseenter:this.handleMouseEnterCounter,onMouseleave:this.handleMouseLeaveCounter,disabled:r})):void 0,v;if(p){let e=this.selectedOptions.length-a;e>0&&(v=j(`div`,{class:`${s}-base-selection-tag-wrapper`,key:`__counter__`},j(bt,{size:n,ref:`counterRef`,onMouseenter:this.handleMouseEnterCounter,disabled:r},{default:()=>`+${e}`})))}let y=f?i?j(be,{ref:`overflowRef`,updateCounter:this.updateCounter,getCounter:this.getCounter,getTail:this.getTail,style:{width:`100%`,display:`flex`,overflow:`hidden`}},{default:o,counter:_,tail:()=>l}):j(be,{ref:`overflowRef`,updateCounter:this.updateCounter,getCounter:this.getCounter,style:{width:`100%`,display:`flex`,overflow:`hidden`}},{default:o,counter:_}):p&&v?o().concat(v):o(),b=m?()=>j(`div`,{class:`${s}-base-selection-popover`},f?o():this.selectedOptions.map(t)):void 0,x=m?Object.assign({show:this.showTagsPanel,trigger:`hover`,overlap:!0,placement:`top`,width:`trigger`,onUpdateShow:this.onPopoverUpdateShow,theme:this.mergedTheme.peers.Popover,themeOverrides:this.mergedTheme.peerOverrides.Popover},c):null,C=!this.selected&&(!this.active||!this.pattern&&!this.isComposing)?j(`div`,{class:`${s}-base-selection-placeholder ${s}-base-selection-overlay`},j(`div`,{class:`${s}-base-selection-placeholder__inner`},this.placeholder)):null,w=i?j(`div`,{ref:`patternInputWrapperRef`,class:`${s}-base-selection-tags`},y,f?null:l,h):j(`div`,{ref:`multipleElRef`,class:`${s}-base-selection-tags`,tabindex:r?void 0:0},y,h);g=j(N,null,m?j(S,Object.assign({},x,{scrollable:!0,style:`max-height: calc(var(--v-target-height) * 6.6);`}),{trigger:()=>w,default:b}):w,C)}else if(i){let e=this.pattern||this.isComposing,t=this.active?!e:!this.selected,n=this.active?!1:this.selected;g=j(`div`,{ref:`patternInputWrapperRef`,class:`${s}-base-selection-label`,title:this.patternInputFocused?void 0:Se(this.label)},j(`input`,Object.assign({},this.inputProps,{ref:`patternInputRef`,class:`${s}-base-selection-input`,value:this.active?this.pattern:``,placeholder:``,readonly:r,disabled:r,tabindex:-1,autofocus:this.autofocus,onFocus:this.handlePatternInputFocus,onBlur:this.handlePatternInputBlur,onInput:this.handlePatternInputInput,onCompositionstart:this.handleCompositionStart,onCompositionend:this.handleCompositionEnd})),n?j(`div`,{class:`${s}-base-selection-label__render-label ${s}-base-selection-overlay`,key:`input`},j(`div`,{class:`${s}-base-selection-overlay__wrapper`},u?u({option:this.selectedOption,handleClose:()=>{}}):d?d(this.selectedOption,!0):A(this.label,this.selectedOption,!0))):null,t?j(`div`,{class:`${s}-base-selection-placeholder ${s}-base-selection-overlay`,key:`placeholder`},j(`div`,{class:`${s}-base-selection-overlay__wrapper`},this.filterablePlaceholder)):null,h)}else g=j(`div`,{ref:`singleElRef`,class:`${s}-base-selection-label`,tabindex:this.disabled?void 0:0},this.label===void 0?j(`div`,{class:`${s}-base-selection-placeholder ${s}-base-selection-overlay`,key:`placeholder`},j(`div`,{class:`${s}-base-selection-placeholder__inner`},this.placeholder)):j(`div`,{class:`${s}-base-selection-input`,title:Se(this.label),key:`input`},j(`div`,{class:`${s}-base-selection-input__content`},u?u({option:this.selectedOption,handleClose:()=>{}}):d?d(this.selectedOption,!0):A(this.label,this.selectedOption,!0))),h);return j(`div`,{ref:`selfRef`,class:[`${s}-base-selection`,this.rtlEnabled&&`${s}-base-selection--rtl`,this.themeClass,e&&`${s}-base-selection--${e}-status`,{[`${s}-base-selection--active`]:this.active,[`${s}-base-selection--selected`]:this.selected||this.active&&this.pattern,[`${s}-base-selection--disabled`]:this.disabled,[`${s}-base-selection--multiple`]:this.multiple,[`${s}-base-selection--focus`]:this.focused}],style:this.cssVars,onClick:this.onClick,onMouseenter:this.handleMouseEnter,onMouseleave:this.handleMouseLeave,onKeydown:this.onKeydown,onFocusin:this.handleFocusin,onFocusout:this.handleFocusout,onMousedown:this.handleMouseDown},g,o?j(`div`,{class:`${s}-base-selection__border`}):null,o?j(`div`,{class:`${s}-base-selection__state-border`}):null)}});function Ct(e){return e.type===`group`}function wt(e){return e.type===`ignored`}function Tt(e,t){try{return!!(1+t.toString().toLowerCase().indexOf(e.trim().toLowerCase()))}catch{return!1}}function Et(e,t){return{getIsGroup:Ct,getIgnored:wt,getKey(t){return Ct(t)?t.name||t.key||`key-required`:t[e]},getChildren(e){return e[t]}}}function Dt(e,t,n,r){if(!t)return e;function i(e){if(!Array.isArray(e))return[];let a=[];for(let o of e)if(Ct(o)){let e=i(o[r]);e.length&&a.push(Object.assign({},o,{[r]:e}))}else if(wt(o))continue;else t(n,o)&&a.push(o);return a}return i(e)}function Ot(e,t,n){let r=new Map;return e.forEach(e=>{Ct(e)?e[n].forEach(e=>{r.set(e[t],e)}):r.set(e[t],e)}),r}var kt=z([X(`select`,`
 z-index: auto;
 outline: none;
 width: 100%;
 position: relative;
 font-weight: var(--n-font-weight);
 `),X(`select-menu`,`
 margin: 4px 0;
 box-shadow: var(--n-menu-box-shadow);
 `,[v({originalTransition:`background-color .3s var(--n-bezier), box-shadow .3s var(--n-bezier)`})])]),At=L({name:`Select`,props:Object.assign(Object.assign({},F.props),{to:m.propTo,bordered:{type:Boolean,default:void 0},clearable:Boolean,clearCreatedOptionsOnClear:{type:Boolean,default:!0},clearFilterAfterSelect:{type:Boolean,default:!0},options:{type:Array,default:()=>[]},defaultValue:{type:[String,Number,Array],default:null},keyboard:{type:Boolean,default:!0},value:[String,Number,Array],placeholder:String,menuProps:Object,multiple:Boolean,size:String,menuSize:{type:String},filterable:Boolean,disabled:{type:Boolean,default:void 0},remote:Boolean,loading:Boolean,filter:Function,placement:{type:String,default:`bottom-start`},widthMode:{type:String,default:`trigger`},tag:Boolean,onCreate:Function,fallbackOption:{type:[Function,Boolean],default:void 0},show:{type:Boolean,default:void 0},showArrow:{type:Boolean,default:!0},maxTagCount:[Number,String],ellipsisTagPopoverProps:Object,consistentMenuWidth:{type:Boolean,default:!0},virtualScroll:{type:Boolean,default:!0},labelField:{type:String,default:`label`},valueField:{type:String,default:`value`},childrenField:{type:String,default:`children`},renderLabel:Function,renderOption:Function,renderTag:Function,"onUpdate:value":[Function,Array],inputProps:Object,nodeProps:Function,ignoreComposition:{type:Boolean,default:!0},showOnFocus:Boolean,onUpdateValue:[Function,Array],onBlur:[Function,Array],onClear:[Function,Array],onFocus:[Function,Array],onScroll:[Function,Array],onSearch:[Function,Array],onUpdateShow:[Function,Array],"onUpdate:show":[Function,Array],displayDirective:{type:String,default:`show`},resetMenuOnOptionsChange:{type:Boolean,default:!0},status:String,showCheckmark:{type:Boolean,default:!0},scrollbarProps:Object,onChange:[Function,Array],items:Array}),slots:Object,setup(t){let{mergedClsPrefixRef:n,mergedBorderedRef:r,namespaceRef:i,inlineThemeDisabled:a,mergedComponentPropsRef:o}=O(t),c=F(`Select`,`-select`,kt,re,t,n),l=W(t.defaultValue),u=e(Q(t,`value`),l),f=W(!1),p=W(``),_=C(t,[`items`,`options`]),v=W([]),y=W([]),b=M(()=>y.value.concat(v.value).concat(_.value)),S=M(()=>{let{filter:e}=t;if(e)return e;let{labelField:n,valueField:r}=t;return(e,t)=>{if(!t)return!1;let i=t[n];if(typeof i==`string`)return Tt(e,i);let a=t[r];return typeof a==`string`?Tt(e,a):typeof a==`number`?Tt(e,String(a)):!1}}),w=M(()=>{if(t.remote)return _.value;{let{value:e}=b,{value:n}=p;return!n.length||!t.filterable?e:Dt(e,S.value,n,t.childrenField)}}),ee=M(()=>{let{valueField:e,childrenField:n}=t,r=Et(e,n);return ot(w.value,r)}),T=M(()=>Ot(b.value,t.valueField,t.childrenField)),E=W(!1),D=e(Q(t,`show`),E),k=W(null),A=W(null),j=W(null),{localeRef:te}=h(`Select`),ne=M(()=>t.placeholder??te.value.placeholder),N=[],P=W(new Map),I=M(()=>{let{fallbackOption:e}=t;if(e===void 0){let{labelField:e,valueField:n}=t;return t=>({[e]:String(t),[n]:t})}return e===!1?!1:t=>Object.assign(e(t),{value:t})});function L(e){let n=t.remote,{value:r}=P,{value:i}=T,{value:a}=I,o=[];return e.forEach(e=>{if(i.has(e))o.push(i.get(e));else if(n&&r.has(e))o.push(r.get(e));else if(a){let t=a(e);t&&o.push(t)}}),o}let R=M(()=>{if(t.multiple){let{value:e}=u;return Array.isArray(e)?L(e):[]}return null}),ae=M(()=>{let{value:e}=u;return!t.multiple&&!Array.isArray(e)?e===null?null:L([e])[0]||null:null}),z=d(t,{mergedSize:e=>{let{size:n}=t;if(n)return n;let{mergedSize:r}=e||{};return r?.value?r.value:o?.value?.Select?.size||`medium`}}),{mergedSizeRef:oe,mergedDisabledRef:B,mergedStatusRef:V}=z;function H(e,n){let{onChange:r,"onUpdate:value":i,onUpdateValue:a}=t,{nTriggerFormChange:o,nTriggerFormInput:c}=z;r&&s(r,e,n),a&&s(a,e,n),i&&s(i,e,n),l.value=e,o(),c()}function U(e){let{onBlur:n}=t,{nTriggerFormBlur:r}=z;n&&s(n,e),r()}function le(){let{onClear:e}=t;e&&s(e)}function ue(e){let{onFocus:n,showOnFocus:r}=t,{nTriggerFormFocus:i}=z;n&&s(n,e),i(),r&&q()}function G(e){let{onSearch:n}=t;n&&s(n,e)}function de(e){let{onScroll:n}=t;n&&s(n,e)}function K(){var e;let{remote:n,multiple:r}=t;if(n){let{value:n}=P;if(r){let{valueField:r}=t;(e=R.value)==null||e.forEach(e=>{n.set(e[r],e)})}else{let e=ae.value;e&&n.set(e[t.valueField],e)}}}function fe(e){let{onUpdateShow:n,"onUpdate:show":r}=t;n&&s(n,e),r&&s(r,e),E.value=e}function q(){B.value||(fe(!0),E.value=!0,t.filterable&&je())}function J(){fe(!1)}function pe(){p.value=``,y.value=N}let Y=W(!1);function me(){t.filterable&&(Y.value=!0)}function he(){t.filterable&&(Y.value=!1,D.value||pe())}function ge(){B.value||(D.value?t.filterable?je():J():q())}function X(e){(j.value?.selfRef)?.contains(e.relatedTarget)||(f.value=!1,U(e),J())}function Z(e){ue(e),f.value=!0}function ve(){f.value=!0}function $(e){k.value?.$el.contains(e.relatedTarget)||(f.value=!1,U(e),J())}function ye(){var e;(e=k.value)==null||e.focus(),J()}function be(e){D.value&&(k.value?.$el.contains(se(e))||J())}function xe(e){if(!Array.isArray(e))return[];if(I.value)return Array.from(e);{let{remote:n}=t,{value:r}=T;if(n){let{value:t}=P;return e.filter(e=>r.has(e)||t.has(e))}else return e.filter(e=>r.has(e))}}function Se(e){Ce(e.rawNode)}function Ce(e){if(B.value)return;let{tag:n,remote:r,clearFilterAfterSelect:i,valueField:a}=t;if(n&&!r){let{value:e}=y,t=e[0]||null;if(t){let e=v.value;e.length?e.push(t):v.value=[t],y.value=N}}if(r&&P.value.set(e[a],e),t.multiple){let t=xe(u.value),o=t.findIndex(t=>t===e[a]);if(~o){if(t.splice(o,1),n&&!r){let t=we(e[a]);~t&&(v.value.splice(t,1),i&&(p.value=``))}}else t.push(e[a]),i&&(p.value=``);H(t,L(t))}else{if(n&&!r){let t=we(e[a]);~t?v.value=[v.value[t]]:v.value=N}Ae(),J(),H(e[a],e)}}function we(e){return v.value.findIndex(n=>n[t.valueField]===e)}function Te(e){D.value||q();let{value:n}=e.target;p.value=n;let{tag:r,remote:i}=t;if(G(n),r&&!i){if(!n){y.value=N;return}let{onCreate:e}=t,r=e?e(n):{[t.labelField]:n,[t.valueField]:n},{valueField:i,labelField:a}=t;_.value.some(e=>e[i]===r[i]||e[a]===r[a])||v.value.some(e=>e[i]===r[i]||e[a]===r[a])?y.value=N:y.value=[r]}}function Ee(e){e.stopPropagation();let{multiple:n,tag:r,remote:i,clearCreatedOptionsOnClear:a}=t;!n&&t.filterable&&J(),r&&!i&&a&&(v.value=N),le(),n?H([],[]):H(null,null)}function De(e){!x(e,`action`)&&!x(e,`empty`)&&!x(e,`header`)&&e.preventDefault()}function Oe(e){de(e)}function ke(e){var n,r,i;if(!t.keyboard){e.preventDefault();return}switch(e.key){case` `:if(t.filterable)break;e.preventDefault();case`Enter`:if(!k.value?.isComposing){if(D.value){let e=j.value?.getPendingTmNode();e?Se(e):t.filterable||(J(),Ae())}else if(q(),t.tag&&Y.value){let e=y.value[0];if(e){let n=e[t.valueField],{value:r}=u;t.multiple&&Array.isArray(r)&&r.includes(n)||Ce(e)}}}e.preventDefault();break;case`ArrowUp`:if(e.preventDefault(),t.loading)return;D.value&&((n=j.value)==null||n.prev());break;case`ArrowDown`:if(e.preventDefault(),t.loading)return;D.value?(r=j.value)==null||r.next():q();break;case`Escape`:D.value&&(g(e),J()),(i=k.value)==null||i.focus();break}}function Ae(){var e;(e=k.value)==null||e.focus()}function je(){var e;(e=k.value)==null||e.focusInput()}function Me(){var e;D.value&&((e=A.value)==null||e.syncPosition())}K(),_e(Q(t,`options`),K);let Ne={focus:()=>{var e;(e=k.value)==null||e.focus()},focusInput:()=>{var e;(e=k.value)==null||e.focusInput()},blur:()=>{var e;(e=k.value)==null||e.blur()},blurInput:()=>{var e;(e=k.value)==null||e.blurInput()}},Pe=M(()=>{let{self:{menuBoxShadow:e}}=c.value;return{"--n-menu-box-shadow":e}}),Fe=a?ie(`select`,void 0,Pe,t):void 0;return Object.assign(Object.assign({},Ne),{mergedStatus:V,mergedClsPrefix:n,mergedBordered:r,namespace:i,treeMate:ee,isMounted:ce(),triggerRef:k,menuRef:j,pattern:p,uncontrolledShow:E,mergedShow:D,adjustedTo:m(t),uncontrolledValue:l,mergedValue:u,followerRef:A,localizedPlaceholder:ne,selectedOption:ae,selectedOptions:R,mergedSize:oe,mergedDisabled:B,focused:f,activeWithoutMenuOpen:Y,inlineThemeDisabled:a,onTriggerInputFocus:me,onTriggerInputBlur:he,handleTriggerOrMenuResize:Me,handleMenuFocus:ve,handleMenuBlur:$,handleMenuTabOut:ye,handleTriggerClick:ge,handleToggle:Se,handleDeleteOption:Ce,handlePatternInput:Te,handleClear:Ee,handleTriggerBlur:X,handleTriggerFocus:Z,handleKeydown:ke,handleMenuAfterLeave:pe,handleMenuClickOutside:be,handleMenuScroll:Oe,handleMenuKeydown:ke,handleMenuMousedown:De,mergedTheme:c,cssVars:a?void 0:Pe,themeClass:Fe?.themeClass,onRender:Fe?.onRender})},render(){return j(`div`,{class:`${this.mergedClsPrefix}-select`},j(p,null,{default:()=>[j(r,null,{default:()=>j(St,{ref:`triggerRef`,inlineThemeDisabled:this.inlineThemeDisabled,status:this.mergedStatus,inputProps:this.inputProps,clsPrefix:this.mergedClsPrefix,showArrow:this.showArrow,maxTagCount:this.maxTagCount,ellipsisTagPopoverProps:this.ellipsisTagPopoverProps,bordered:this.mergedBordered,active:this.activeWithoutMenuOpen||this.mergedShow,pattern:this.pattern,placeholder:this.localizedPlaceholder,selectedOption:this.selectedOption,selectedOptions:this.selectedOptions,multiple:this.multiple,renderTag:this.renderTag,renderLabel:this.renderLabel,filterable:this.filterable,clearable:this.clearable,disabled:this.mergedDisabled,size:this.mergedSize,theme:this.mergedTheme.peers.InternalSelection,labelField:this.labelField,valueField:this.valueField,themeOverrides:this.mergedTheme.peerOverrides.InternalSelection,loading:this.loading,focused:this.focused,onClick:this.handleTriggerClick,onDeleteOption:this.handleDeleteOption,onPatternInput:this.handlePatternInput,onClear:this.handleClear,onBlur:this.handleTriggerBlur,onFocus:this.handleTriggerFocus,onKeydown:this.handleKeydown,onPatternBlur:this.onTriggerInputBlur,onPatternFocus:this.onTriggerInputFocus,onResize:this.handleTriggerOrMenuResize,ignoreComposition:this.ignoreComposition},{arrow:()=>{var e;return[(e=this.$slots).arrow?.call(e)]}})}),j(a,{ref:`followerRef`,show:this.mergedShow,to:this.adjustedTo,teleportDisabled:this.adjustedTo===m.tdkey,containerClass:this.namespace,width:this.consistentMenuWidth?`target`:void 0,minWidth:`target`,placement:this.placement},{default:()=>j(E,{name:`fade-in-scale-up-transition`,appear:this.isMounted,onAfterLeave:this.handleMenuAfterLeave},{default:()=>{var e;return this.mergedShow||this.displayDirective===`show`?((e=this.onRender)==null||e.call(this),fe(j(pt,Object.assign({},this.menuProps,{ref:`menuRef`,onResize:this.handleTriggerOrMenuResize,inlineThemeDisabled:this.inlineThemeDisabled,virtualScroll:this.consistentMenuWidth&&this.virtualScroll,class:[`${this.mergedClsPrefix}-select-menu`,this.themeClass,this.menuProps?.class],clsPrefix:this.mergedClsPrefix,focusable:!0,labelField:this.labelField,valueField:this.valueField,autoPending:!0,nodeProps:this.nodeProps,theme:this.mergedTheme.peers.InternalSelectMenu,themeOverrides:this.mergedTheme.peerOverrides.InternalSelectMenu,treeMate:this.treeMate,multiple:this.multiple,size:this.menuSize,renderOption:this.renderOption,renderLabel:this.renderLabel,value:this.mergedValue,style:[this.menuProps?.style,this.cssVars],onToggle:this.handleToggle,onScroll:this.handleMenuScroll,onFocus:this.handleMenuFocus,onBlur:this.handleMenuBlur,onKeydown:this.handleMenuKeydown,onTabOut:this.handleMenuTabOut,onMousedown:this.handleMenuMousedown,show:this.mergedShow,showCheckmark:this.showCheckmark,resetMenuOnOptionsChange:this.resetMenuOnOptionsChange,scrollbarProps:this.scrollbarProps}),{empty:()=>{var e;return[(e=this.$slots).empty?.call(e)]},header:()=>{var e;return[(e=this.$slots).header?.call(e)]},action:()=>{var e;return[(e=this.$slots).action?.call(e)]}}),this.displayDirective===`show`?[[ue,this.mergedShow],[o,this.handleMenuClickOutside,void 0,{capture:!0}]]:[[o,this.handleMenuClickOutside,void 0,{capture:!0}]])):null}})})]}))}});export{At as t};
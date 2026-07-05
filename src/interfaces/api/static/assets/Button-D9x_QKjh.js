import{C as e,S as t,c as n,d as r,g as i,h as a,l as o,s,u as c,v as l,x as u}from"./ErrorBanner-DLePGqf1.js";import{C as d,Ct as f,Et as p,Jt as m,Mt as h,Nt as g,Tt as _,Vt as v,Xt as y,Zt as b,_t as x,bt as S,d as C,en as w,gt as T,ht as E,rn as D,ut as O,vt as k,wn as A,wt as j,x as M,xn as N,xt as P}from"./index-DcgR8lOt.js";var F=typeof document<`u`&&typeof window<`u`,I=m({name:`FadeInExpandTransition`,props:{appear:Boolean,group:Boolean,mode:String,onLeave:Function,onAfterLeave:Function,onAfterEnter:Function,width:Boolean,reverse:Boolean},setup(e,{slots:t}){function n(t){e.width?t.style.maxWidth=`${t.offsetWidth}px`:t.style.maxHeight=`${t.offsetHeight}px`,t.offsetWidth}function r(t){e.width?t.style.maxWidth=`0`:t.style.maxHeight=`0`,t.offsetWidth;let{onLeave:n}=e;n&&n()}function i(t){e.width?t.style.maxWidth=``:t.style.maxHeight=``;let{onAfterLeave:n}=e;n&&n()}function a(t){if(t.style.transition=`none`,e.width){let e=t.offsetWidth;t.style.maxWidth=`0`,t.offsetWidth,t.style.transition=``,t.style.maxWidth=`${e}px`}else if(e.reverse)t.style.maxHeight=`${t.offsetHeight}px`,t.offsetHeight,t.style.transition=``,t.style.maxHeight=`0`;else{let e=t.offsetHeight;t.style.maxHeight=`0`,t.offsetWidth,t.style.transition=``,t.style.maxHeight=`${e}px`}t.offsetWidth}function o(t){var n;e.width?t.style.maxWidth=``:e.reverse||(t.style.maxHeight=``),(n=e.onAfterEnter)==null||n.call(e)}return()=>{let{group:s,width:c,appear:l,mode:u}=e,d=s?g:h,f={name:c?`fade-in-width-expand-transition`:`fade-in-height-expand-transition`,appear:l,onEnter:a,onAfterEnter:o,onBeforeLeave:n,onLeave:r,onAfterLeave:i};return s||(f.mode=u),y(d,f,t)}}}),{cubicBezierEaseInOut:L}=d;function R({duration:e=`.2s`,delay:t=`.1s`}={}){return[S(`&.fade-in-width-expand-transition-leave-from, &.fade-in-width-expand-transition-enter-to`,{opacity:1}),S(`&.fade-in-width-expand-transition-leave-to, &.fade-in-width-expand-transition-enter-from`,`
 opacity: 0!important;
 margin-left: 0!important;
 margin-right: 0!important;
 `),S(`&.fade-in-width-expand-transition-leave-active`,`
 overflow: hidden;
 transition:
 opacity ${e} ${L},
 max-width ${e} ${L} ${t},
 margin-left ${e} ${L} ${t},
 margin-right ${e} ${L} ${t};
 `),S(`&.fade-in-width-expand-transition-enter-active`,`
 overflow: hidden;
 transition:
 opacity ${e} ${L} ${t},
 max-width ${e} ${L},
 margin-left ${e} ${L},
 margin-right ${e} ${L};
 `)]}var z=P(`base-wave`,`
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 border-radius: inherit;
`),B=m({name:`BaseWave`,props:{clsPrefix:{type:String,required:!0}},setup(e){c(`-base-wave`,z,A(e,`clsPrefix`));let t=N(null),n=N(!1),r=null;return D(()=>{r!==null&&window.clearTimeout(r)}),{active:n,selfRef:t,play(){r!==null&&(window.clearTimeout(r),n.value=!1,r=null),w(()=>{var e;(e=t.value)==null||e.offsetHeight,n.value=!0,r=window.setTimeout(()=>{n.value=!1,r=null},1e3)})}}},render(){let{clsPrefix:e}=this;return y(`div`,{ref:`selfRef`,"aria-hidden":!0,class:[`${e}-base-wave`,this.active&&`${e}-base-wave--active`]})}}),V=F&&`chrome`in window;F&&navigator.userAgent.includes(`Firefox`);var H=F&&navigator.userAgent.includes(`Safari`)&&!V;function U(e){return k(e,[255,255,255,.16])}function W(e){return k(e,[0,0,0,.12])}var G=E(`n-button-group`),K=S([P(`button`,`
 margin: 0;
 font-weight: var(--n-font-weight);
 line-height: 1;
 font-family: inherit;
 padding: var(--n-padding);
 height: var(--n-height);
 font-size: var(--n-font-size);
 border-radius: var(--n-border-radius);
 color: var(--n-text-color);
 background-color: var(--n-color);
 width: var(--n-width);
 white-space: nowrap;
 outline: none;
 position: relative;
 z-index: auto;
 border: none;
 display: inline-flex;
 flex-wrap: nowrap;
 flex-shrink: 0;
 align-items: center;
 justify-content: center;
 user-select: none;
 -webkit-user-select: none;
 text-align: center;
 cursor: pointer;
 text-decoration: none;
 transition:
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 opacity .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `,[j(`color`,[f(`border`,{borderColor:`var(--n-border-color)`}),j(`disabled`,[f(`border`,{borderColor:`var(--n-border-color-disabled)`})]),_(`disabled`,[S(`&:focus`,[f(`state-border`,{borderColor:`var(--n-border-color-focus)`})]),S(`&:hover`,[f(`state-border`,{borderColor:`var(--n-border-color-hover)`})]),S(`&:active`,[f(`state-border`,{borderColor:`var(--n-border-color-pressed)`})]),j(`pressed`,[f(`state-border`,{borderColor:`var(--n-border-color-pressed)`})])])]),j(`disabled`,{backgroundColor:`var(--n-color-disabled)`,color:`var(--n-text-color-disabled)`},[f(`border`,{border:`var(--n-border-disabled)`})]),_(`disabled`,[S(`&:focus`,{backgroundColor:`var(--n-color-focus)`,color:`var(--n-text-color-focus)`},[f(`state-border`,{border:`var(--n-border-focus)`})]),S(`&:hover`,{backgroundColor:`var(--n-color-hover)`,color:`var(--n-text-color-hover)`},[f(`state-border`,{border:`var(--n-border-hover)`})]),S(`&:active`,{backgroundColor:`var(--n-color-pressed)`,color:`var(--n-text-color-pressed)`},[f(`state-border`,{border:`var(--n-border-pressed)`})]),j(`pressed`,{backgroundColor:`var(--n-color-pressed)`,color:`var(--n-text-color-pressed)`},[f(`state-border`,{border:`var(--n-border-pressed)`})])]),j(`loading`,`cursor: wait;`),P(`base-wave`,`
 pointer-events: none;
 top: 0;
 right: 0;
 bottom: 0;
 left: 0;
 animation-iteration-count: 1;
 animation-duration: var(--n-ripple-duration);
 animation-timing-function: var(--n-bezier-ease-out), var(--n-bezier-ease-out);
 `,[j(`active`,{zIndex:1,animationName:`button-wave-spread, button-wave-opacity`})]),F&&`MozBoxSizing`in document.createElement(`div`).style?S(`&::moz-focus-inner`,{border:0}):null,f(`border, state-border`,`
 position: absolute;
 left: 0;
 top: 0;
 right: 0;
 bottom: 0;
 border-radius: inherit;
 transition: border-color .3s var(--n-bezier);
 pointer-events: none;
 `),f(`border`,`
 border: var(--n-border);
 `),f(`state-border`,`
 border: var(--n-border);
 border-color: #0000;
 z-index: 1;
 `),f(`icon`,`
 margin: var(--n-icon-margin);
 margin-left: 0;
 height: var(--n-icon-size);
 width: var(--n-icon-size);
 max-width: var(--n-icon-size);
 font-size: var(--n-icon-size);
 position: relative;
 flex-shrink: 0;
 `,[P(`icon-slot`,`
 height: var(--n-icon-size);
 width: var(--n-icon-size);
 position: absolute;
 left: 0;
 top: 50%;
 transform: translateY(-50%);
 display: flex;
 align-items: center;
 justify-content: center;
 `,[n({top:`50%`,originalTransform:`translateY(-50%)`})]),R()]),f(`content`,`
 display: flex;
 align-items: center;
 flex-wrap: nowrap;
 min-width: 0;
 `,[S(`~`,[f(`icon`,{margin:`var(--n-icon-margin)`,marginRight:0})])]),j(`block`,`
 display: flex;
 width: 100%;
 `),j(`dashed`,[f(`border, state-border`,{borderStyle:`dashed !important`})]),j(`disabled`,{cursor:`not-allowed`,opacity:`var(--n-opacity-disabled)`})]),S(`@keyframes button-wave-spread`,{from:{boxShadow:`0 0 0.5px 0 var(--n-ripple-color)`},to:{boxShadow:`0 0 0.5px 4.5px var(--n-ripple-color)`}}),S(`@keyframes button-wave-opacity`,{from:{opacity:`var(--n-wave-opacity)`},to:{opacity:0}})]),q=m({name:`Button`,props:Object.assign(Object.assign({},M.props),{color:String,textColor:String,text:Boolean,block:Boolean,loading:Boolean,disabled:Boolean,circle:Boolean,size:String,ghost:Boolean,round:Boolean,secondary:Boolean,tertiary:Boolean,quaternary:Boolean,strong:Boolean,focusable:{type:Boolean,default:!0},keyboard:{type:Boolean,default:!0},tag:{type:String,default:`button`},type:{type:String,default:`default`},dashed:Boolean,renderIcon:Function,iconPlacement:{type:String,default:`left`},attrType:{type:String,default:`button`},bordered:{type:Boolean,default:!0},onClick:[Function,Array],nativeFocusBehavior:{type:Boolean,default:!H},spinProps:Object}),slots:Object,setup(n){let o=N(null),s=N(null),c=N(!1),l=T(()=>!n.quaternary&&!n.tertiary&&!n.secondary&&!n.text&&(!n.color||n.ghost||n.dashed)&&n.bordered),u=b(G,{}),{inlineThemeDisabled:d,mergedClsPrefixRef:f,mergedRtlRef:m,mergedComponentPropsRef:h}=O(n),{mergedSizeRef:g}=a({},{defaultSize:`medium`,mergedSize:e=>{let{size:t}=n;if(t)return t;let{size:r}=u;if(r)return r;let{mergedSize:i}=e||{};return i?i.value:h?.value?.Button?.size||`medium`}}),_=v(()=>n.focusable&&!n.disabled),y=e=>{var t;_.value||e.preventDefault(),!n.nativeFocusBehavior&&(e.preventDefault(),!n.disabled&&_.value&&((t=o.value)==null||t.focus({preventScroll:!0})))},S=e=>{var r;if(!n.disabled&&!n.loading){let{onClick:i}=n;i&&t(i,e),n.text||(r=s.value)==null||r.play()}},w=e=>{switch(e.key){case`Enter`:if(!n.keyboard)return;c.value=!1}},E=e=>{switch(e.key){case`Enter`:if(!n.keyboard||n.loading){e.preventDefault();return}c.value=!0}},D=()=>{c.value=!1},k=M(`Button`,`-button`,K,C,n,f),A=r(`Button`,m,f),j=v(()=>{let{common:{cubicBezierEaseInOut:e,cubicBezierEaseOut:t},self:r}=k.value,{rippleDuration:i,opacityDisabled:a,fontWeight:o,fontWeightStrong:s}=r,c=g.value,{dashed:l,type:u,ghost:d,text:f,color:m,round:h,circle:_,textColor:v,secondary:y,tertiary:b,quaternary:S,strong:C}=n,w={"--n-font-weight":C?s:o},T={"--n-color":`initial`,"--n-color-hover":`initial`,"--n-color-pressed":`initial`,"--n-color-focus":`initial`,"--n-color-disabled":`initial`,"--n-ripple-color":`initial`,"--n-text-color":`initial`,"--n-text-color-hover":`initial`,"--n-text-color-pressed":`initial`,"--n-text-color-focus":`initial`,"--n-text-color-disabled":`initial`},E=u===`tertiary`,D=u==="default",O=E?`default`:u;if(f){let e=v||m;T={"--n-color":`#0000`,"--n-color-hover":`#0000`,"--n-color-pressed":`#0000`,"--n-color-focus":`#0000`,"--n-color-disabled":`#0000`,"--n-ripple-color":`#0000`,"--n-text-color":e||r[p(`textColorText`,O)],"--n-text-color-hover":e?U(e):r[p(`textColorTextHover`,O)],"--n-text-color-pressed":e?W(e):r[p(`textColorTextPressed`,O)],"--n-text-color-focus":e?U(e):r[p(`textColorTextHover`,O)],"--n-text-color-disabled":e||r[p(`textColorTextDisabled`,O)]}}else if(d||l){let e=v||m;T={"--n-color":`#0000`,"--n-color-hover":`#0000`,"--n-color-pressed":`#0000`,"--n-color-focus":`#0000`,"--n-color-disabled":`#0000`,"--n-ripple-color":m||r[p(`rippleColor`,O)],"--n-text-color":e||r[p(`textColorGhost`,O)],"--n-text-color-hover":e?U(e):r[p(`textColorGhostHover`,O)],"--n-text-color-pressed":e?W(e):r[p(`textColorGhostPressed`,O)],"--n-text-color-focus":e?U(e):r[p(`textColorGhostHover`,O)],"--n-text-color-disabled":e||r[p(`textColorGhostDisabled`,O)]}}else if(y){let e=D?r.textColor:E?r.textColorTertiary:r[p(`color`,O)],t=m||e,n=u!=="default"&&u!==`tertiary`;T={"--n-color":n?x(t,{alpha:Number(r.colorOpacitySecondary)}):r.colorSecondary,"--n-color-hover":n?x(t,{alpha:Number(r.colorOpacitySecondaryHover)}):r.colorSecondaryHover,"--n-color-pressed":n?x(t,{alpha:Number(r.colorOpacitySecondaryPressed)}):r.colorSecondaryPressed,"--n-color-focus":n?x(t,{alpha:Number(r.colorOpacitySecondaryHover)}):r.colorSecondaryHover,"--n-color-disabled":r.colorSecondary,"--n-ripple-color":`#0000`,"--n-text-color":t,"--n-text-color-hover":t,"--n-text-color-pressed":t,"--n-text-color-focus":t,"--n-text-color-disabled":t}}else if(b||S){let e=D?r.textColor:E?r.textColorTertiary:r[p(`color`,O)],t=m||e;b?(T[`--n-color`]=r.colorTertiary,T[`--n-color-hover`]=r.colorTertiaryHover,T[`--n-color-pressed`]=r.colorTertiaryPressed,T[`--n-color-focus`]=r.colorSecondaryHover,T[`--n-color-disabled`]=r.colorTertiary):(T[`--n-color`]=r.colorQuaternary,T[`--n-color-hover`]=r.colorQuaternaryHover,T[`--n-color-pressed`]=r.colorQuaternaryPressed,T[`--n-color-focus`]=r.colorQuaternaryHover,T[`--n-color-disabled`]=r.colorQuaternary),T[`--n-ripple-color`]=`#0000`,T[`--n-text-color`]=t,T[`--n-text-color-hover`]=t,T[`--n-text-color-pressed`]=t,T[`--n-text-color-focus`]=t,T[`--n-text-color-disabled`]=t}else T={"--n-color":m||r[p(`color`,O)],"--n-color-hover":m?U(m):r[p(`colorHover`,O)],"--n-color-pressed":m?W(m):r[p(`colorPressed`,O)],"--n-color-focus":m?U(m):r[p(`colorFocus`,O)],"--n-color-disabled":m||r[p(`colorDisabled`,O)],"--n-ripple-color":m||r[p(`rippleColor`,O)],"--n-text-color":v||(m?r.textColorPrimary:E?r.textColorTertiary:r[p(`textColor`,O)]),"--n-text-color-hover":v||(m?r.textColorHoverPrimary:r[p(`textColorHover`,O)]),"--n-text-color-pressed":v||(m?r.textColorPressedPrimary:r[p(`textColorPressed`,O)]),"--n-text-color-focus":v||(m?r.textColorFocusPrimary:r[p(`textColorFocus`,O)]),"--n-text-color-disabled":v||(m?r.textColorDisabledPrimary:r[p(`textColorDisabled`,O)])};let A={"--n-border":`initial`,"--n-border-hover":`initial`,"--n-border-pressed":`initial`,"--n-border-focus":`initial`,"--n-border-disabled":`initial`};A=f?{"--n-border":`none`,"--n-border-hover":`none`,"--n-border-pressed":`none`,"--n-border-focus":`none`,"--n-border-disabled":`none`}:{"--n-border":r[p(`border`,O)],"--n-border-hover":r[p(`borderHover`,O)],"--n-border-pressed":r[p(`borderPressed`,O)],"--n-border-focus":r[p(`borderFocus`,O)],"--n-border-disabled":r[p(`borderDisabled`,O)]};let{[p(`height`,c)]:j,[p(`fontSize`,c)]:M,[p(`padding`,c)]:N,[p(`paddingRound`,c)]:P,[p(`iconSize`,c)]:F,[p(`borderRadius`,c)]:I,[p(`iconMargin`,c)]:L,waveOpacity:R}=r,z={"--n-width":_&&!f?j:`initial`,"--n-height":f?`initial`:j,"--n-font-size":M,"--n-padding":_||f?`initial`:h?P:N,"--n-icon-size":F,"--n-icon-margin":L,"--n-border-radius":f?`initial`:_||h?j:I};return Object.assign(Object.assign(Object.assign(Object.assign({"--n-bezier":e,"--n-bezier-ease-out":t,"--n-ripple-duration":i,"--n-opacity-disabled":a,"--n-wave-opacity":R},w),T),A),z)}),P=d?i(`button`,v(()=>{let t=``,{dashed:r,type:i,ghost:a,text:o,color:s,round:c,circle:l,textColor:u,secondary:d,tertiary:f,quaternary:p,strong:m}=n;r&&(t+=`a`),a&&(t+=`b`),o&&(t+=`c`),c&&(t+=`d`),l&&(t+=`e`),d&&(t+=`f`),f&&(t+=`g`),p&&(t+=`h`),m&&(t+=`i`),s&&(t+=`j${e(s)}`),u&&(t+=`k${e(u)}`);let{value:h}=g;return t+=`l${h[0]}`,t+=`m${i[0]}`,t}),j,n):void 0;return{selfElRef:o,waveElRef:s,mergedClsPrefix:f,mergedFocusable:_,mergedSize:g,showBorder:l,enterPressed:c,rtlEnabled:A,handleMousedown:y,handleKeydown:E,handleBlur:D,handleKeyup:w,handleClick:S,customColorCssVars:v(()=>{let{color:e}=n;if(!e)return null;let t=U(e);return{"--n-border-color":e,"--n-border-color-hover":t,"--n-border-color-pressed":W(e),"--n-border-color-focus":t,"--n-border-color-disabled":e}}),cssVars:d?void 0:j,themeClass:P?.themeClass,onRender:P?.onRender}},render(){let{mergedClsPrefix:e,tag:t,onRender:n}=this;n?.();let r=u(this.$slots.default,t=>t&&y(`span`,{class:`${e}-button__content`},t));return y(t,{ref:`selfElRef`,class:[this.themeClass,`${e}-button`,`${e}-button--${this.type}-type`,`${e}-button--${this.mergedSize}-type`,this.rtlEnabled&&`${e}-button--rtl`,this.disabled&&`${e}-button--disabled`,this.block&&`${e}-button--block`,this.enterPressed&&`${e}-button--pressed`,!this.text&&this.dashed&&`${e}-button--dashed`,this.color&&`${e}-button--color`,this.secondary&&`${e}-button--secondary`,this.loading&&`${e}-button--loading`,this.ghost&&`${e}-button--ghost`],tabindex:this.mergedFocusable?0:-1,type:this.attrType,style:this.cssVars,disabled:this.disabled,onClick:this.handleClick,onBlur:this.handleBlur,onMousedown:this.handleMousedown,onKeyup:this.handleKeyup,onKeydown:this.handleKeydown},this.iconPlacement===`right`&&r,y(I,{width:!0},{default:()=>u(this.$slots.icon,t=>(this.loading||this.renderIcon||t)&&y(`span`,{class:`${e}-button__icon`,style:{margin:l(this.$slots.default)?`0`:``}},y(o,null,{default:()=>this.loading?y(s,Object.assign({clsPrefix:e,key:`loading`,class:`${e}-icon-slot`,strokeWidth:20},this.spinProps)):y(`div`,{key:`icon`,class:`${e}-icon-slot`,role:`none`},this.renderIcon?this.renderIcon():t)})))}),this.iconPlacement===`left`&&r,this.text?null:y(B,{ref:`waveElRef`,clsPrefix:e}),this.showBorder?y(`div`,{"aria-hidden":!0,class:`${e}-button__border`,style:this.customColorCssVars}):null,this.showBorder?y(`div`,{"aria-hidden":!0,class:`${e}-button__state-border`,style:this.customColorCssVars}):null)}}),J=q;export{J as n,H as r,q as t};
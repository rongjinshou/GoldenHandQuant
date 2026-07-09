import{a as e,c as t,l as n,r,u as i}from"./PageHeader-BUq5Rf13.js";import{$ as a,$n as o,Cn as s,Gt as c,Kn as l,Ln as u,O as d,Q as f,Sn as p,U as m,V as h,Wn as g,Wt as _,Xn as v,Y as y,_n as b,an as x,bn as S,et as C,hr as w,ln as T,qn as E,rn as D,tt as O,un as k,vn as A,vr as j,xn as M,z as N}from"./index-DSFz8UXu.js";var P=typeof document<`u`&&typeof window<`u`,{cubicBezierEaseInOut:F}=C;function I({duration:e=`.2s`,delay:t=`.1s`}={}){return[b(`&.fade-in-width-expand-transition-leave-from, &.fade-in-width-expand-transition-enter-to`,{opacity:1}),b(`&.fade-in-width-expand-transition-leave-to, &.fade-in-width-expand-transition-enter-from`,`
 opacity: 0!important;
 margin-left: 0!important;
 margin-right: 0!important;
 `),b(`&.fade-in-width-expand-transition-leave-active`,`
 overflow: hidden;
 transition:
 opacity ${e} ${F},
 max-width ${e} ${F} ${t},
 margin-left ${e} ${F} ${t},
 margin-right ${e} ${F} ${t};
 `),b(`&.fade-in-width-expand-transition-enter-active`,`
 overflow: hidden;
 transition:
 opacity ${e} ${F} ${t},
 max-width ${e} ${F},
 margin-left ${e} ${F},
 margin-right ${e} ${F};
 `)]}var L=A(`base-wave`,`
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 border-radius: inherit;
`),R=g({name:`BaseWave`,props:{clsPrefix:{type:String,required:!0}},setup(e){a(`-base-wave`,L,j(e,`clsPrefix`));let t=w(null),n=w(!1),r=null;return o(()=>{r!==null&&window.clearTimeout(r)}),{active:n,selfRef:t,play(){r!==null&&(window.clearTimeout(r),n.value=!1,r=null),v(()=>{var e;(e=t.value)==null||e.offsetHeight,n.value=!0,r=window.setTimeout(()=>{n.value=!1,r=null},1e3)})}}},render(){let{clsPrefix:e}=this;return l(`div`,{ref:`selfRef`,"aria-hidden":!0,class:[`${e}-base-wave`,this.active&&`${e}-base-wave--active`]})}}),z=P&&`chrome`in window;P&&navigator.userAgent.includes(`Firefox`);var B=P&&navigator.userAgent.includes(`Safari`)&&!z;function V(e){return k(e,[255,255,255,.16])}function H(e){return k(e,[0,0,0,.12])}var U=D(`n-button-group`),W=b([A(`button`,`
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
 `,[M(`color`,[S(`border`,{borderColor:`var(--n-border-color)`}),M(`disabled`,[S(`border`,{borderColor:`var(--n-border-color-disabled)`})]),p(`disabled`,[b(`&:focus`,[S(`state-border`,{borderColor:`var(--n-border-color-focus)`})]),b(`&:hover`,[S(`state-border`,{borderColor:`var(--n-border-color-hover)`})]),b(`&:active`,[S(`state-border`,{borderColor:`var(--n-border-color-pressed)`})]),M(`pressed`,[S(`state-border`,{borderColor:`var(--n-border-color-pressed)`})])])]),M(`disabled`,{backgroundColor:`var(--n-color-disabled)`,color:`var(--n-text-color-disabled)`},[S(`border`,{border:`var(--n-border-disabled)`})]),p(`disabled`,[b(`&:focus`,{backgroundColor:`var(--n-color-focus)`,color:`var(--n-text-color-focus)`},[S(`state-border`,{border:`var(--n-border-focus)`})]),b(`&:hover`,{backgroundColor:`var(--n-color-hover)`,color:`var(--n-text-color-hover)`},[S(`state-border`,{border:`var(--n-border-hover)`})]),b(`&:active`,{backgroundColor:`var(--n-color-pressed)`,color:`var(--n-text-color-pressed)`},[S(`state-border`,{border:`var(--n-border-pressed)`})]),M(`pressed`,{backgroundColor:`var(--n-color-pressed)`,color:`var(--n-text-color-pressed)`},[S(`state-border`,{border:`var(--n-border-pressed)`})])]),M(`loading`,`cursor: wait;`),A(`base-wave`,`
 pointer-events: none;
 top: 0;
 right: 0;
 bottom: 0;
 left: 0;
 animation-iteration-count: 1;
 animation-duration: var(--n-ripple-duration);
 animation-timing-function: var(--n-bezier-ease-out), var(--n-bezier-ease-out);
 `,[M(`active`,{zIndex:1,animationName:`button-wave-spread, button-wave-opacity`})]),P&&`MozBoxSizing`in document.createElement(`div`).style?b(`&::moz-focus-inner`,{border:0}):null,S(`border, state-border`,`
 position: absolute;
 left: 0;
 top: 0;
 right: 0;
 bottom: 0;
 border-radius: inherit;
 transition: border-color .3s var(--n-bezier);
 pointer-events: none;
 `),S(`border`,`
 border: var(--n-border);
 `),S(`state-border`,`
 border: var(--n-border);
 border-color: #0000;
 z-index: 1;
 `),S(`icon`,`
 margin: var(--n-icon-margin);
 margin-left: 0;
 height: var(--n-icon-size);
 width: var(--n-icon-size);
 max-width: var(--n-icon-size);
 font-size: var(--n-icon-size);
 position: relative;
 flex-shrink: 0;
 `,[A(`icon-slot`,`
 height: var(--n-icon-size);
 width: var(--n-icon-size);
 position: absolute;
 left: 0;
 top: 50%;
 transform: translateY(-50%);
 display: flex;
 align-items: center;
 justify-content: center;
 `,[m({top:`50%`,originalTransform:`translateY(-50%)`})]),I()]),S(`content`,`
 display: flex;
 align-items: center;
 flex-wrap: nowrap;
 min-width: 0;
 `,[b(`~`,[S(`icon`,{margin:`var(--n-icon-margin)`,marginRight:0})])]),M(`block`,`
 display: flex;
 width: 100%;
 `),M(`dashed`,[S(`border, state-border`,{borderStyle:`dashed !important`})]),M(`disabled`,{cursor:`not-allowed`,opacity:`var(--n-opacity-disabled)`})]),b(`@keyframes button-wave-spread`,{from:{boxShadow:`0 0 0.5px 0 var(--n-ripple-color)`},to:{boxShadow:`0 0 0.5px 4.5px var(--n-ripple-color)`}}),b(`@keyframes button-wave-opacity`,{from:{opacity:`var(--n-wave-opacity)`},to:{opacity:0}})]),G=g({name:`Button`,props:Object.assign(Object.assign({},f.props),{color:String,textColor:String,text:Boolean,block:Boolean,loading:Boolean,disabled:Boolean,circle:Boolean,size:String,ghost:Boolean,round:Boolean,secondary:Boolean,tertiary:Boolean,quaternary:Boolean,strong:Boolean,focusable:{type:Boolean,default:!0},keyboard:{type:Boolean,default:!0},tag:{type:String,default:`button`},type:{type:String,default:`default`},dashed:Boolean,renderIcon:Function,iconPlacement:{type:String,default:`left`},attrType:{type:String,default:`button`},bordered:{type:Boolean,default:!0},onClick:[Function,Array],nativeFocusBehavior:{type:Boolean,default:!B},spinProps:Object}),slots:Object,setup(e){let t=w(null),a=w(null),o=w(!1),l=x(()=>!e.quaternary&&!e.tertiary&&!e.secondary&&!e.text&&(!e.color||e.ghost||e.dashed)&&e.bordered),p=E(U,{}),{inlineThemeDisabled:m,mergedClsPrefixRef:h,mergedRtlRef:g,mergedComponentPropsRef:v}=c(e),{mergedSizeRef:y}=r({},{defaultSize:`medium`,mergedSize:t=>{let{size:n}=e;if(n)return n;let{size:r}=p;if(r)return r;let{mergedSize:i}=t||{};return i?i.value:v?.value?.Button?.size||`medium`}}),b=u(()=>e.focusable&&!e.disabled),S=n=>{var r;b.value||n.preventDefault(),!e.nativeFocusBehavior&&(n.preventDefault(),!e.disabled&&b.value&&((r=t.value)==null||r.focus({preventScroll:!0})))},C=t=>{var r;if(!e.disabled&&!e.loading){let{onClick:i}=e;i&&n(i,t),e.text||(r=a.value)==null||r.play()}},D=t=>{switch(t.key){case`Enter`:if(!e.keyboard)return;o.value=!1}},k=t=>{switch(t.key){case`Enter`:if(!e.keyboard||e.loading){t.preventDefault();return}o.value=!0}},A=()=>{o.value=!1},j=f(`Button`,`-button`,W,d,e,h),M=O(`Button`,g,h),N=u(()=>{let{common:{cubicBezierEaseInOut:t,cubicBezierEaseOut:n},self:r}=j.value,{rippleDuration:i,opacityDisabled:a,fontWeight:o,fontWeightStrong:c}=r,l=y.value,{dashed:u,type:d,ghost:f,text:p,color:m,round:h,circle:g,textColor:_,secondary:v,tertiary:b,quaternary:x,strong:S}=e,C={"--n-font-weight":S?c:o},w={"--n-color":`initial`,"--n-color-hover":`initial`,"--n-color-pressed":`initial`,"--n-color-focus":`initial`,"--n-color-disabled":`initial`,"--n-ripple-color":`initial`,"--n-text-color":`initial`,"--n-text-color-hover":`initial`,"--n-text-color-pressed":`initial`,"--n-text-color-focus":`initial`,"--n-text-color-disabled":`initial`},E=d===`tertiary`,D=d==="default",O=E?`default`:d;if(p){let e=_||m;w={"--n-color":`#0000`,"--n-color-hover":`#0000`,"--n-color-pressed":`#0000`,"--n-color-focus":`#0000`,"--n-color-disabled":`#0000`,"--n-ripple-color":`#0000`,"--n-text-color":e||r[s(`textColorText`,O)],"--n-text-color-hover":e?V(e):r[s(`textColorTextHover`,O)],"--n-text-color-pressed":e?H(e):r[s(`textColorTextPressed`,O)],"--n-text-color-focus":e?V(e):r[s(`textColorTextHover`,O)],"--n-text-color-disabled":e||r[s(`textColorTextDisabled`,O)]}}else if(f||u){let e=_||m;w={"--n-color":`#0000`,"--n-color-hover":`#0000`,"--n-color-pressed":`#0000`,"--n-color-focus":`#0000`,"--n-color-disabled":`#0000`,"--n-ripple-color":m||r[s(`rippleColor`,O)],"--n-text-color":e||r[s(`textColorGhost`,O)],"--n-text-color-hover":e?V(e):r[s(`textColorGhostHover`,O)],"--n-text-color-pressed":e?H(e):r[s(`textColorGhostPressed`,O)],"--n-text-color-focus":e?V(e):r[s(`textColorGhostHover`,O)],"--n-text-color-disabled":e||r[s(`textColorGhostDisabled`,O)]}}else if(v){let e=D?r.textColor:E?r.textColorTertiary:r[s(`color`,O)],t=m||e,n=d!=="default"&&d!==`tertiary`;w={"--n-color":n?T(t,{alpha:Number(r.colorOpacitySecondary)}):r.colorSecondary,"--n-color-hover":n?T(t,{alpha:Number(r.colorOpacitySecondaryHover)}):r.colorSecondaryHover,"--n-color-pressed":n?T(t,{alpha:Number(r.colorOpacitySecondaryPressed)}):r.colorSecondaryPressed,"--n-color-focus":n?T(t,{alpha:Number(r.colorOpacitySecondaryHover)}):r.colorSecondaryHover,"--n-color-disabled":r.colorSecondary,"--n-ripple-color":`#0000`,"--n-text-color":t,"--n-text-color-hover":t,"--n-text-color-pressed":t,"--n-text-color-focus":t,"--n-text-color-disabled":t}}else if(b||x){let e=D?r.textColor:E?r.textColorTertiary:r[s(`color`,O)],t=m||e;b?(w[`--n-color`]=r.colorTertiary,w[`--n-color-hover`]=r.colorTertiaryHover,w[`--n-color-pressed`]=r.colorTertiaryPressed,w[`--n-color-focus`]=r.colorSecondaryHover,w[`--n-color-disabled`]=r.colorTertiary):(w[`--n-color`]=r.colorQuaternary,w[`--n-color-hover`]=r.colorQuaternaryHover,w[`--n-color-pressed`]=r.colorQuaternaryPressed,w[`--n-color-focus`]=r.colorQuaternaryHover,w[`--n-color-disabled`]=r.colorQuaternary),w[`--n-ripple-color`]=`#0000`,w[`--n-text-color`]=t,w[`--n-text-color-hover`]=t,w[`--n-text-color-pressed`]=t,w[`--n-text-color-focus`]=t,w[`--n-text-color-disabled`]=t}else w={"--n-color":m||r[s(`color`,O)],"--n-color-hover":m?V(m):r[s(`colorHover`,O)],"--n-color-pressed":m?H(m):r[s(`colorPressed`,O)],"--n-color-focus":m?V(m):r[s(`colorFocus`,O)],"--n-color-disabled":m||r[s(`colorDisabled`,O)],"--n-ripple-color":m||r[s(`rippleColor`,O)],"--n-text-color":_||(m?r.textColorPrimary:E?r.textColorTertiary:r[s(`textColor`,O)]),"--n-text-color-hover":_||(m?r.textColorHoverPrimary:r[s(`textColorHover`,O)]),"--n-text-color-pressed":_||(m?r.textColorPressedPrimary:r[s(`textColorPressed`,O)]),"--n-text-color-focus":_||(m?r.textColorFocusPrimary:r[s(`textColorFocus`,O)]),"--n-text-color-disabled":_||(m?r.textColorDisabledPrimary:r[s(`textColorDisabled`,O)])};let k={"--n-border":`initial`,"--n-border-hover":`initial`,"--n-border-pressed":`initial`,"--n-border-focus":`initial`,"--n-border-disabled":`initial`};k=p?{"--n-border":`none`,"--n-border-hover":`none`,"--n-border-pressed":`none`,"--n-border-focus":`none`,"--n-border-disabled":`none`}:{"--n-border":r[s(`border`,O)],"--n-border-hover":r[s(`borderHover`,O)],"--n-border-pressed":r[s(`borderPressed`,O)],"--n-border-focus":r[s(`borderFocus`,O)],"--n-border-disabled":r[s(`borderDisabled`,O)]};let{[s(`height`,l)]:A,[s(`fontSize`,l)]:M,[s(`padding`,l)]:N,[s(`paddingRound`,l)]:P,[s(`iconSize`,l)]:F,[s(`borderRadius`,l)]:I,[s(`iconMargin`,l)]:L,waveOpacity:R}=r,z={"--n-width":g&&!p?A:`initial`,"--n-height":p?`initial`:A,"--n-font-size":M,"--n-padding":g||p?`initial`:h?P:N,"--n-icon-size":F,"--n-icon-margin":L,"--n-border-radius":p?`initial`:g||h?A:I};return Object.assign(Object.assign(Object.assign(Object.assign({"--n-bezier":t,"--n-bezier-ease-out":n,"--n-ripple-duration":i,"--n-opacity-disabled":a,"--n-wave-opacity":R},C),w),k),z)}),P=m?_(`button`,u(()=>{let t=``,{dashed:n,type:r,ghost:a,text:o,color:s,round:c,circle:l,textColor:u,secondary:d,tertiary:f,quaternary:p,strong:m}=e;n&&(t+=`a`),a&&(t+=`b`),o&&(t+=`c`),c&&(t+=`d`),l&&(t+=`e`),d&&(t+=`f`),f&&(t+=`g`),p&&(t+=`h`),m&&(t+=`i`),s&&(t+=`j${i(s)}`),u&&(t+=`k${i(u)}`);let{value:h}=y;return t+=`l${h[0]}`,t+=`m${r[0]}`,t}),N,e):void 0;return{selfElRef:t,waveElRef:a,mergedClsPrefix:h,mergedFocusable:b,mergedSize:y,showBorder:l,enterPressed:o,rtlEnabled:M,handleMousedown:S,handleKeydown:k,handleBlur:A,handleKeyup:D,handleClick:C,customColorCssVars:u(()=>{let{color:t}=e;if(!t)return null;let n=V(t);return{"--n-border-color":t,"--n-border-color-hover":n,"--n-border-color-pressed":H(t),"--n-border-color-focus":n,"--n-border-color-disabled":t}}),cssVars:m?void 0:N,themeClass:P?.themeClass,onRender:P?.onRender}},render(){let{mergedClsPrefix:n,tag:r,onRender:i}=this;i?.();let a=t(this.$slots.default,e=>e&&l(`span`,{class:`${n}-button__content`},e));return l(r,{ref:`selfElRef`,class:[this.themeClass,`${n}-button`,`${n}-button--${this.type}-type`,`${n}-button--${this.mergedSize}-type`,this.rtlEnabled&&`${n}-button--rtl`,this.disabled&&`${n}-button--disabled`,this.block&&`${n}-button--block`,this.enterPressed&&`${n}-button--pressed`,!this.text&&this.dashed&&`${n}-button--dashed`,this.color&&`${n}-button--color`,this.secondary&&`${n}-button--secondary`,this.loading&&`${n}-button--loading`,this.ghost&&`${n}-button--ghost`],tabindex:this.mergedFocusable?0:-1,type:this.attrType,style:this.cssVars,disabled:this.disabled,onClick:this.handleClick,onBlur:this.handleBlur,onMousedown:this.handleMousedown,onKeyup:this.handleKeyup,onKeydown:this.handleKeydown},this.iconPlacement===`right`&&a,l(h,{width:!0},{default:()=>t(this.$slots.icon,t=>(this.loading||this.renderIcon||t)&&l(`span`,{class:`${n}-button__icon`,style:{margin:e(this.$slots.default)?`0`:``}},l(y,null,{default:()=>this.loading?l(N,Object.assign({clsPrefix:n,key:`loading`,class:`${n}-icon-slot`,strokeWidth:20},this.spinProps)):l(`div`,{key:`icon`,class:`${n}-icon-slot`,role:`none`},this.renderIcon?this.renderIcon():t)})))}),this.iconPlacement===`left`&&a,this.text?null:l(R,{ref:`waveElRef`,clsPrefix:n}),this.showBorder?l(`div`,{"aria-hidden":!0,class:`${n}-button__border`,style:this.customColorCssVars}):null,this.showBorder?l(`div`,{"aria-hidden":!0,class:`${n}-button__state-border`,style:this.customColorCssVars}):null)}}),K=G;export{P as i,K as n,B as r,G as t};
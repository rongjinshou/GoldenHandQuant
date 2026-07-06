# 运行记录 — ShopHub 设计实现一致性修复

STATUS: DONE

本文件记录本工具一次成功的端到端运行：从**全新未修复**的 ShopHub 材料出发，经 `apply.sh` 施加已验证修复，重新构建并跑通全部公开黑盒用例。

## 运行环境

- JDK 17（Temurin 17.0.19）、Maven 3.9.9
- `maven-settings.xml` 指向 Maven Central（内网镜像不可达时按 README 允许置空）

## 执行步骤与结果

### 1. 释出 pristine 基线并施加修复

从基线 commit `1b1e88f`（pristine ShopHub）释出一份未修复的 `code/`，运行确定性修复引擎：

```
$ bash work/fixer/apply.sh <target-root>
...
apply-report: checked=193  applied(fix)=150  added=31  variant-imposed=0  already-fixed=0  deleted=12  del-absent=0  failed=0
RESULT: OK (all 193 verified fixes are in place)
APPLY_EXIT=0
```

- 修改 150 个文件、新增 31 个文件、删除 12 个文件（模块内影子事件类、cart 的 JPA 实体/仓库、review 死监听器及其测试），无失败。

### 2. 源码一致性校验

修复后的目标 `code/` 与本地**已验证工作树**逐文件比对，除 `target/` 构建产物外**无任何差异**——证明 `apply.sh` 精确复现了通过全部用例的代码状态，而非近似覆盖。

### 3. 构建

```
$ mvn -s maven-settings.xml -f <target>/code/pom.xml install -DskipTests
INSTALL_EXIT=0   （12 个模块全部 BUILD SUCCESS）
```

### 4. 公开黑盒验证

```
$ mvn -s maven-settings.xml -f test-cases/pom.xml test
[INFO] Tests run: 24, Failures: 0, Errors: 0, Skipped: 0
BLACKBOX_EXIT=0
```

`PubBasicFlowTest`（PUB-001..016）+ `PubAdditionalBehaviorTest`（PUB-101..108）**全部通过**。该结果在本地连续 6 次以上运行稳定复现（0 失败、0 错误）。

### 5. 幂等性

对已修复工程再次运行 `apply.sh`：

```
apply-report: checked=193  applied(fix)=0  added=0  variant-imposed=0  already-fixed=181  deleted=0  del-absent=12  failed=0
```

第二次运行为纯空操作，证明引擎幂等、可重复执行。

## 修复结果获取

- 修复后的工程：`apply.sh` 原地写入的 `<target-root>/code/`
- 修复清单与依据：`work/fixer/knowledge-base/findings.md`
- 过程日志：`logs/trace/`

## 结论

从未修复材料到全绿，全流程确定性、无人工干预、可重复。共修复 97 处模块级不一致 + 8 处跨模块集成缺陷，公开黑盒 24/24 通过。

STATUS: DONE

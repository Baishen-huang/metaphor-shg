# -*- coding: utf-8 -*-
"""静态可达性审计：metaphor_graph 包的「谁被调用 / 调用链 / 死代码 / 可疑模式」。

为什么需要它
------------
本项目已**三次**出现「代码存在，但生产路径上从不执行」的缺陷，人工审查反复漏过：

  ① ``hgnn.py`` 的跨层传播从未被检索打分路径调用 —— 打分走
     ``training.extract_features`` + 中心性字典，于是「flat ≡ HGNN」（|ΔAUC| ≤ 0.005）；
  ② ``mipvu.py`` 原实现把桥接门控写死成 semfield 里 6 个级联 id ——
     任何替换级联构造规则（``cascade_rules``）的实验都会**静默关掉整条 MIPVU 通道**；
  ③ ``evaluate_real.py`` 在无 ``LLM_API_KEY`` 时静默回落到 ``LocalHeuristicBackend``，
     该后端不实现 ``discover_batch``/``batch_refine``，于是 ``--llm-cache`` 根本不被消费，
     却仍打印一份看似正常的指标 —— 实测假性 P1 = 0.434（真实 0.092）。

人工审查三次都漏掉了下一处，故改为**机器检查**：本脚本用 ``ast`` 静态解析
``metaphor_graph/`` 全部公开函数与类，报告

  1. 是否被调用（从入口点出发的可达性）；
  2. 调用链（最短路径）；
  3. 分类：生产路径 / 仅测试 / 仅导出 / 孤立；
  4. 可疑模式：硬编码门控 / 静默回落 / 未使用的公开函数 / 参数被忽略。

入口点定义（``_ENTRY_KINDS``）
------------------------------
  ``prod_internal``  metaphor_graph/ 内模块的 ``if __name__ == "__main__"`` 块
                     与模块顶层语句（导入即执行）。
  ``prod_external``  metaphor_graph/ **之外**（``experiments/``、``release/``、仓库根）
                     的同类模块 —— 实验脚本是真实调用方，不计入会把大量活代码误判为死代码。
  ``test``           ``test_metaphor_graph.py``（单独统计，用于「仅测试」分类）。

保守性
------
「假报不可达」比「漏报死代码」代价高得多。因此解析调用点时：

  * 接收者可解析（``self.foo`` / ``mod.foo`` / 已导入符号）→ 精确连边（置信 high）；
  * 接收者不可解析（``x.foo`` 且 ``x`` 是局部量/参数）→ 按方法名做**全局**兜底连边（置信 low）；
  * 名字属于 ``_BUILTIN_METHOD_NAMES``（``encode``/``get``/``append`` 等标准库惯用名）
    且接收者不可解析 → **不**连边，否则 ``json.dumps(...).encode("utf-8")`` 会把
    ``MetaphorHGNN.encode`` 误判为「已被调用」。该白名单是本审计最主要的**假阴性**来源，
    已显式列出，见 ``_BUILTIN_METHOD_NAMES``。

用法
----
    python -m metaphor_graph.audit_reachability                 # 人类可读报告
    python -m metaphor_graph.audit_reachability --json          # JSON 到 stdout
    python -m metaphor_graph.audit_reachability --json out.json # JSON 落盘
    python -m metaphor_graph.audit_reachability --section dead  # 只看死代码
    python -m metaphor_graph.audit_reachability --section patterns

只读静态分析：不导入被审包、不执行被审代码、不联网。退出码恒为 0。
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from collections import defaultdict, deque

# --------------------------------------------------------------------------- 路径

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(PKG_DIR)
PKG_NAME = os.path.basename(PKG_DIR)

#: 除包目录外还要扫描的目录（外部调用方）。``.wt/`` 是 git worktree 副本，必须排除。
EXTERNAL_DIRS = ("experiments", "release")

#: 明确跳过的目录名（相对路径任一段命中即跳过）。
SKIP_DIR_PARTS = {".git", ".wt", "__pycache__", ".venv", "node_modules",
                  ".mypy_cache", ".pytest_cache", "output", "data"}

TEST_BASENAME = "test_metaphor_graph.py"

#: 接收者不可解析时**不**按名字兜底连边的方法名（标准库/内建惯用名）。
#:
#: 用途：避免 ``json.dumps(...).encode("utf-8")`` 把 ``MetaphorHGNN.encode``
#: 误判为「已被调用」。**该白名单只在本项目内不存在同名方法时生效**：
#: 若项目里确有同名方法（如 ``to_dict``/``index``/``load``），说明该名字在本仓库
#: 有真实语义，此时按保守原则**照常连边**（置信 low），宁可高估可达性也不漏报。
#: 这是本审计最主要的假阴性来源，故规则写成显式两段式而非一张黑名单。
_BUILTIN_METHOD_NAMES = frozenset({
    "encode", "decode", "get", "setdefault", "pop", "popitem", "items", "keys",
    "values", "update", "append", "extend", "insert", "remove", "clear", "copy",
    "count", "index", "sort", "reverse", "add", "discard", "union", "intersection",
    "difference", "split", "rsplit", "join", "strip", "lstrip", "rstrip", "replace",
    "startswith", "endswith", "find", "rfind", "format", "format_map", "lower",
    "upper", "title", "capitalize", "zfill", "ljust", "rjust", "center", "read",
    "readline", "readlines", "write", "writelines", "close", "flush", "seek",
    "tell", "fileno", "readable", "writable", "dumps", "loads", "dump", "load",
    "getvalue", "setvalue", "makedirs", "mkdir", "exists", "isfile", "isdir",
    "basename", "dirname", "abspath", "realpath", "normpath", "splitext", "listdir",
    "walk", "glob", "match", "search", "findall", "finditer", "sub", "group",
    "groups", "groupdict", "reshape", "astype", "tolist", "sum", "mean", "std",
    "dot", "norm", "transpose", "squeeze", "expand_dims", "argsort", "argmax",
    "argmin", "clip", "round", "sqrt", "log", "exp", "concatenate", "stack",
    "flatten", "item", "view", "to_dict", "to_json", "from_dict", "from_json",
    "copy_from", "setdefaults", "sort_values", "iterrows", "read_csv", "to_csv",
    "notify", "notify_all", "acquire", "release", "join_thread", "start",
    "terminate", "decode_json", "encode_json", "isoformat", "strftime", "strptime",
    "timestamp", "total_seconds", "hexdigest", "digest", "add_argument",
    "parse_args", "print_help", "assert_called_once", "assertEqual", "assertTrue",
})

#: 「跳过工作」的语句形态 —— 硬编码门控的判定要素之一。
_EMPTY_CTORS = {"list", "dict", "set", "tuple", "frozenset"}

#: 视为「有记录」的调用名（出现在 except 体里即不算静默吞异常）。
_LOGGING_CALLS = {"print", "warn", "warning", "error", "info", "debug", "log",
                  "exception", "critical", "raise"}

#: 类型/结构断言谓词 —— 出现在 `if not <call>:` 里时**不算**降级回落，
#: 否则每个内部一致性检查（`if not isinstance(x, ast.If)`）都会被报成「静默回落」，
#: 噪声淹没信号。降级回落只关心「缺输入 / 缺数据」形态。
_TYPE_PREDICATES = {"isinstance", "issubclass", "hasattr", "callable", "any",
                    "all", "getattr", "set", "len", "isinstance_", "type"}

#: 模式扫描跳过的文件（工具自身的元代码，逐条自报纯属噪声）。
#: 注意：只影响【可疑模式】一节；可达性一节仍覆盖这些文件。
PATTERN_SKIP_FILES = {"metaphor_graph/audit_reachability.py",
                      "metaphor_graph/audit_fairness.py",
                      "metaphor_graph/inventory.py"}

#: 门控字面量的低危特征 —— 命中则标 low（词表 / CLI 分支 / 消融开关），
#: 否则标 review（需要人工判断是否为「静默关闭整条通道」型缺陷）。
_LOW_RISK_CONST_HINTS = ("STOP", "NOISE", "SKIP", "PUNCT", "MARKER", "WORD",
                         "FILLER", "BLACKLIST", "WHITELIST", "SEEDS")

#: 外部框架通过**名字约定**回调的方法（不由本项目显式调用）。
#: 这些方法由 ast.NodeVisitor / http.server / unittest 在运行期派发，
#: 静态调用图看不见，必须显式当作入口点，否则会被误报为死代码。
_FRAMEWORK_HOOK_PREFIXES = ("visit_", "do_", "handle_", "log_", "test_")
_FRAMEWORK_HOOK_EXACT = {"setUp", "tearDown", "setUpClass", "tearDownClass",
                         "default", "runTest"}


# =========================================================================== 模型


class DefNode:
    """一个被审计的定义（函数 / 方法 / 类）。"""

    __slots__ = ("nid", "file", "module", "qualname", "name", "kind", "lineno",
                 "has_doc", "params", "decorators", "bases", "is_public",
                 "is_method", "enclosing_class", "in_test_file", "in_pkg",
                 "body_node", "locals", "unused_params", "call_site_count",
                 "loop_if_ids")

    def __init__(self, nid, file, module, qualname, name, kind, lineno, has_doc,
                 params, decorators, bases, enclosing_class, in_pkg, body_node):
        self.nid = nid
        self.file = file
        self.module = module
        self.qualname = qualname
        self.name = name
        self.kind = kind                    # "function" | "method" | "class"
        self.lineno = lineno
        self.has_doc = has_doc
        self.params = params                # [str]
        self.decorators = decorators        # [str]
        self.bases = bases                  # [str]
        self.enclosing_class = enclosing_class
        self.in_pkg = in_pkg
        self.body_node = body_node
        self.is_method = kind == "method"
        self.is_public = not name.startswith("_")
        self.in_test_file = file.endswith(TEST_BASENAME)
        self.locals = set()
        self.unused_params = []
        self.call_site_count = 0
        self.loop_if_ids = frozenset()


class Site:
    """一个调用点 / 引用点。"""

    __slots__ = ("file", "owner", "lineno", "chain", "is_call", "locals", "cls_hint")

    def __init__(self, file, owner, lineno, chain, is_call, locals_, cls_hint=None):
        self.file = file
        self.owner = owner          # 所属 DefNode.nid，模块顶层为 ""
        self.lineno = lineno
        self.chain = chain          # ["a","b","c"] 或 None（无法解析的表达式）
        self.is_call = is_call
        self.locals = locals_       # 该作用域内的局部名（含参数）
        self.cls_hint = cls_hint    # 实例化后立即调用时的类名（`Foo().bar`）


# =========================================================================== 工具


def _posix(p: str) -> str:
    return p.replace(os.sep, "/")


def _iter_py_files():
    """产出 (绝对路径, 相对项目根的 posix 路径)，排除 worktree / 缓存目录。"""
    seen = set()

    def walk(root, allow_outside):
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if d not in SKIP_DIR_PARTS and not d.startswith(".")]
            for fn in sorted(filenames):
                if not fn.endswith(".py"):
                    continue
                full = os.path.join(dirpath, fn)
                rel = _posix(os.path.relpath(full, PROJECT_DIR))
                if rel in seen:
                    continue
                seen.add(rel)
                yield full, rel

    yield from walk(PKG_DIR, False)
    for sub in EXTERNAL_DIRS:
        d = os.path.join(PROJECT_DIR, sub)
        if os.path.isdir(d):
            yield from walk(d, True)
    # 仓库根的一级 .py（若有）
    for fn in sorted(os.listdir(PROJECT_DIR)):
        if fn.endswith(".py"):
            full = os.path.join(PROJECT_DIR, fn)
            rel = _posix(fn)
            if rel not in seen:
                seen.add(rel)
                yield full, rel


def _dotted_module(rel: str) -> str:
    """相对路径 → 尽力而为的点分模块名（无 __init__.py 的目录也照样拼）。"""
    parts = rel[:-3].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _is_pkg_init(rel: str) -> bool:
    return rel.endswith("__init__.py")


def _attr_chain(node):
    """``a.b.c`` → ``["a","b","c"]``；根不是 Name 则返回 None。"""
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        parts.reverse()
        return parts
    return None


def _call_chain(node):
    """解析**调用目标**表达式，比 ``_attr_chain`` 多认「实例化后立即调用」。

    返回 ``(chain, cls_hint, is_instance_call)``：

      ``foo``              → (["foo"], None, False)
      ``mod.foo``          → (["mod","foo"], None, False)
      ``Foo().foo``        → (["Foo","foo"], "Foo", True)   ← 本项目里很常见
      ``super().foo``      → (["super","foo"], "super", True)
      ``a.b().foo``        → (["a","b","foo"], "b", True)

    链式调用若不做这一步会整条丢失（``MetaphorScorer().fit(ds)`` 的 ``fit``
    会被静默漏掉，把活的训练路径误报成死代码）。
    """
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        parts.reverse()
        return parts, None, False
    if isinstance(cur, ast.Call):
        inner = cur.func
        if isinstance(inner, ast.Name):
            parts.reverse()
            return [inner.id] + parts, inner.id, True
        ch = _attr_chain(inner)
        if ch:
            parts.reverse()
            return ch + parts, ch[-1], True
    return None, None, False


def _empty_value(node) -> bool:
    """判断表达式是否是「空/降级」返回值：None / "" / False / [] / {} / set() …"""
    if node is None:
        return True
    if isinstance(node, ast.Constant):
        v = node.value
        return v is None or v is False or v == ""
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return len(node.elts) == 0
    if isinstance(node, ast.Dict):
        return len(node.keys) == 0
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id in _EMPTY_CTORS and not node.args
    return False


def _skip_stmts(stmts) -> bool:
    """语句序列是否含「跳过工作」的语句（continue/break/pass/return 空值）。"""
    for s in stmts:
        if isinstance(s, (ast.Continue, ast.Break, ast.Pass)):
            return True
        if isinstance(s, ast.Return) and _empty_value(s.value):
            return True
    return False


def _has_raise_or_log(stmts) -> bool:
    """语句序列里是否有 raise 或日志/打印（有则不算「静默」）。"""
    for s in stmts:
        for sub in ast.walk(s):
            if isinstance(sub, ast.Raise):
                return True
            if isinstance(sub, ast.Call):
                f = sub.func
                nm = f.attr if isinstance(f, ast.Attribute) else (
                    f.id if isinstance(f, ast.Name) else None)
                if nm in _LOGGING_CALLS:
                    return True
    return False


def _is_main_guard(node) -> bool:
    """``if __name__ == "__main__":`` （两种操作数顺序都认）。"""
    if not isinstance(node, ast.If):
        return False
    t = node.test
    if not isinstance(t, ast.Compare) or len(t.ops) != 1:
        return False
    if not isinstance(t.ops[0], ast.Eq):
        return False
    lhs, rhs = t.left, t.comparators[0]

    def is_name_main(n):
        return isinstance(n, ast.Name) and n.id == "__name__"

    def is_str_main(n):
        return isinstance(n, ast.Constant) and n.value == "__main__"

    return (is_name_main(lhs) and is_str_main(rhs)) or \
           (is_str_main(lhs) and is_name_main(rhs))


def _collect_loop_ifs(fn) -> set:
    """收集函数体内**位于循环中**的 If 节点（按 id()）。

    用于区分「循环内逐项过滤」（正常）与「函数级通道门控」（可疑）。
    """
    out = set()
    for sub in ast.walk(fn):
        if isinstance(sub, (ast.For, ast.AsyncFor, ast.While)):
            for inner in ast.walk(sub):
                if isinstance(inner, ast.If):
                    out.add(id(inner))
    return out


def _collect_locals(fn) -> set:
    """函数作用域内的绑定名（参数 + 赋值 + for/with/except/comprehension 目标）。"""
    out = set()
    a = fn.args
    for arg in list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs):
        out.add(arg.arg)
    if a.vararg:
        out.add(a.vararg.arg)
    if a.kwarg:
        out.add(a.kwarg.arg)
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Assign):
            for t in sub.targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        out.add(n.id)
        elif isinstance(sub, (ast.AnnAssign, ast.AugAssign)):
            for n in ast.walk(sub.target):
                if isinstance(n, ast.Name):
                    out.add(n.id)
        elif isinstance(sub, (ast.For, ast.AsyncFor)):
            for n in ast.walk(sub.target):
                if isinstance(n, ast.Name):
                    out.add(n.id)
        elif isinstance(sub, (ast.With, ast.AsyncWith)):
            for item in sub.items:
                if item.optional_vars is not None:
                    for n in ast.walk(item.optional_vars):
                        if isinstance(n, ast.Name):
                            out.add(n.id)
        elif isinstance(sub, ast.ExceptHandler) and sub.name:
            out.add(sub.name)
        elif isinstance(sub, ast.NamedExpr):
            for n in ast.walk(sub.target):
                if isinstance(n, ast.Name):
                    out.add(n.id)
        elif isinstance(sub, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for gen in sub.generators:
                for n in ast.walk(gen.target):
                    if isinstance(n, ast.Name):
                        out.add(n.id)
        elif isinstance(sub, (ast.Global, ast.Nonlocal)):
            out.update(sub.names)
    return out


def _decorator_names(fn) -> list:
    out = []
    for d in getattr(fn, "decorator_list", []):
        if isinstance(d, ast.Name):
            out.append(d.id)
        elif isinstance(d, ast.Attribute):
            out.append(d.attr)
        elif isinstance(d, ast.Call):
            f = d.func
            out.append(f.attr if isinstance(f, ast.Attribute) else
                       (f.id if isinstance(f, ast.Name) else ""))
    return [x for x in out if x]


# =========================================================================== 解析


class _ModuleParser(ast.NodeVisitor):
    """遍历一个模块，收集定义、调用点/引用点、导入表。"""

    def __init__(self, rel, module, tree):
        self.rel = rel
        self.module = module
        self.tree = tree
        self.defs = []                  # [DefNode]
        self.sites = []                 # [Site]
        self.mod_aliases = {}           # alias -> dotted module
        self.sym_aliases = {}           # alias -> (dotted module, symbol)
        self.star_modules = []          # [dotted module]
        self._owner = ""                # 当前所属定义（"" = 模块顶层）
        self._locals = set()
        self._class_stack = []

    # ---- 定义

    def _qual(self, name):
        if self._class_stack:
            return ".".join(self._class_stack + [name])
        return name

    def visit_ClassDef(self, node):
        q = self._qual(node.name)
        nid = f"{self.rel}::{q}"
        bases = []
        for b in node.bases:
            ch = _attr_chain(b) if isinstance(b, ast.Attribute) else None
            if ch:
                bases.append(".".join(ch))
            elif isinstance(b, ast.Name):
                bases.append(b.id)
        d = DefNode(nid, self.rel, self.module, q, node.name, "class", node.lineno,
                    ast.get_docstring(node) is not None, [], _decorator_names(node),
                    bases, ".".join(self._class_stack) or None, True, node)
        self.defs.append(d)
        prev_owner, prev_locals = self._owner, self._locals
        self._owner, self._locals = nid, set()
        self._class_stack.append(node.name)
        for stmt in node.body:
            self.visit(stmt)
        self._class_stack.pop()
        self._owner, self._locals = prev_owner, prev_locals

    def _visit_func(self, node):
        q = self._qual(node.name)
        nid = f"{self.rel}::{q}"
        params = [a.arg for a in
                  list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs)]
        if node.args.vararg:
            params.append(node.args.vararg.arg)
        if node.args.kwarg:
            params.append(node.args.kwarg.arg)
        kind = "method" if self._class_stack else "function"
        d = DefNode(nid, self.rel, self.module, q, node.name, kind, node.lineno,
                    ast.get_docstring(node) is not None, params,
                    _decorator_names(node), [],
                    ".".join(self._class_stack) or None, True, node)
        self.defs.append(d)
        # 嵌套函数：owner 归到最内层，避免把内层调用记到外层头上
        prev_owner, prev_locals = self._owner, self._locals
        self._owner = nid
        self._locals = _collect_locals(node)
        d.locals = set(self._locals)
        for stmt in node.body:
            self.visit(stmt)
        self._owner, self._locals = prev_owner, prev_locals

    visit_FunctionDef = _visit_func
    visit_AsyncFunctionDef = _visit_func

    def visit_Lambda(self, node):
        # lambda 不建节点，但其内部调用归属当前 owner
        self.visit(node.body)

    # ---- 调用 / 引用

    def visit_Call(self, node):
        chain, cls_hint, is_inst = _call_chain(node.func)
        if chain is None and isinstance(node.func, (ast.Name, ast.Attribute)):
            chain = _attr_chain(node.func)
        self.sites.append(Site(self.rel, self._owner, node.lineno, chain, True,
                               set(self._locals), cls_hint))
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.sites.append(Site(self.rel, self._owner, node.lineno,
                                   [node.id], False, set(self._locals)))
        self.generic_visit(node)

    def visit_Attribute(self, node):
        chain = _attr_chain(node)
        if chain and len(chain) > 1:
            self.sites.append(Site(self.rel, self._owner, node.lineno, chain,
                                   False, set(self._locals)))
        self.generic_visit(node)

    # ---- 导入

    def visit_Import(self, node):
        for a in node.names:
            if a.asname:
                self.mod_aliases[a.asname] = a.name
            else:
                self.mod_aliases[a.name.split(".")[0]] = a.name.split(".")[0]

    def visit_ImportFrom(self, node):
        target = _resolve_relative(self.module, _is_pkg_init(self.rel),
                                   node.level or 0, node.module or "")
        for a in node.names:
            if a.name == "*":
                self.star_modules.append(target)
                continue
            self.sym_aliases[a.asname or a.name] = (target, a.name)


def _resolve_relative(mod_dotted, is_pkg, level, module) -> str:
    """把 `from ... import` 的目标解析为点分模块名。

    level == 0 → **绝对导入**，module 原样返回（早期版本在这里错误地把当前包
    前缀又拼了一次，导致 `from metaphor_graph import embeddings as _emb` 解析成
    `metaphor_graph.metaphor_graph`，整条 embedding 通道被判死代码）。
    level > 0 → 相对导入，按层数回退。
    """
    if not level:
        return module
    parts = mod_dotted.split(".") if mod_dotted else []
    if not is_pkg:
        parts = parts[:-1]
    drop = level - 1
    if drop:
        parts = parts[:-drop] if drop <= len(parts) else []
    if module:
        parts = parts + module.split(".")
    return ".".join(parts)


# =========================================================================== 图


class ReachabilityAudit:
    """可达性 + 可疑模式审计。"""

    def __init__(self, root_dir=None):
        self.pkg_dir = root_dir or PKG_DIR
        self.files = {}                 # rel -> abs
        self.trees = {}                 # rel -> ast.Module
        self.modules = {}               # dotted -> rel
        self.parsers = {}               # rel -> _ModuleParser
        self.defs = {}                  # nid -> DefNode
        self.by_file = defaultdict(dict)      # rel -> {qualname: nid}
        self.by_name = defaultdict(list)      # simple name -> [nid]
        self.by_method_name = defaultdict(list)
        self.mod_tail = defaultdict(set)      # 模块名末段 -> {rel}（sys.path hack 兜底）
        self.edges = defaultdict(set)          # nid -> {nid}（含弱边，保守口径）
        self.edge_conf = {}                    # (src, dst) -> "high"|"low"
        self.site_edges = []                   # 明细（供报告）
        self.roots = {"prod_internal": set(), "prod_external": set(), "test": set()}
        self.exported = set()
        self.unresolved_calls = defaultdict(int)
        self.errors = []
        self._scanned = False

    # ---------------------------------------------------------------- 扫描

    def scan(self):
        if self._scanned:
            return self
        self._scanned = True
        for full, rel in _iter_py_files():
            try:
                src = open(full, encoding="utf-8").read()
                tree = ast.parse(src, filename=full)
            except (SyntaxError, UnicodeDecodeError, OSError) as e:  # pragma: no cover
                self.errors.append(f"{rel}: {type(e).__name__}: {e}")
                continue
            self.files[rel] = full
            self.trees[rel] = tree
            dotted = _dotted_module(rel)
            self.modules.setdefault(dotted, rel)
            if _is_pkg_init(rel):
                self.modules[dotted] = rel
            self.mod_tail[dotted.split(".")[-1]].add(rel)
            p = _ModuleParser(rel, dotted, tree)
            p.visit(tree)
            self.parsers[rel] = p
            for d in p.defs:
                d.in_pkg = rel.startswith(PKG_NAME + "/")
                self.defs[d.nid] = d
                self.by_file[rel][d.qualname] = d.nid
                self.by_name[d.name].append(d.nid)
                if d.is_method:
                    self.by_method_name[d.name].append(d.nid)
        self._collect_roots()
        self._build_edges()
        self._count_call_sites()
        self._find_unused_params()
        return self

    # ---------------------------------------------------------------- 入口点

    def _collect_roots(self):
        for rel, tree in self.trees.items():
            in_pkg = rel.startswith(PKG_NAME + "/")
            is_test = rel.endswith(TEST_BASENAME)
            kind = "test" if is_test else ("prod_internal" if in_pkg else "prod_external")
            if is_test:
                # 测试文件：全部定义都是根（保守；测试辅助函数也算入口）
                for d in self.parsers[rel].defs:
                    self.roots["test"].add(d.nid)
            else:
                self.roots[kind].add(f"{rel}::<toplevel>")
            for node in tree.body:
                if _is_main_guard(node):
                    self.roots[kind].add(f"{rel}::<main>")
        # 框架钩子：类继承自**项目之外**的框架基类（ast.NodeVisitor /
        # http.server.BaseHTTPRequestHandler / unittest.TestCase …），其方法由框架
        # 按名字约定在运行期回调，静态调用图看不见 → 显式当作入口点，
        # 否则 visit_Call / do_POST 会被误报为死代码。
        # 测试文件整体已在 roots["test"] 里，不再重复登记为生产入口
        # （否则 `test_*` 前缀会把 300 个测试方法灌进生产根，令整包几乎全可达）。
        for nid, d in self.defs.items():
            if not d.is_method or d.in_test_file:
                continue
            if not (d.name in _FRAMEWORK_HOOK_EXACT or
                    d.name.startswith(_FRAMEWORK_HOOK_PREFIXES)):
                continue
            cls = self.defs.get(f"{d.file}::{d.enclosing_class}")
            if cls is None:
                continue
            external = False
            for b in cls.bases:
                simple = b.split(".")[-1]
                if not any(x.kind == "class" and x.name == simple
                           for x in self.defs.values()):
                    external = True
                    break
            if external:
                self.roots["prod_internal" if d.in_pkg else "prod_external"].add(nid)
        # 对外公开 API 的约定名：`to_dict` 等序列化出口通常由**本项目之外的**
        # 调用方（导出脚本 / Neo4j 导入器 / 用户代码）调用，静态看不见。
        # 本项目里这类方法确实被 `.to_dict()` 属性访问调用（见 _resolve 的兜底），
        # 故不额外加根，靠调用图即可覆盖。
        # __init__.py 的导出
        for rel, tree in self.trees.items():
            if not rel.startswith(PKG_NAME + "/") or not _is_pkg_init(rel):
                continue
            p = self.parsers[rel]
            names = set()
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name) and t.id == "__all__":
                            for e in ast.walk(node.value):
                                if isinstance(e, ast.Constant) and isinstance(e.value, str):
                                    names.add(e.value)
            for alias, (mod, sym) in p.sym_aliases.items():
                names.add(alias)
                tid = f"{self.modules.get(mod, mod + '.py')}::{sym}"
                if tid in self.defs:
                    self.exported.add(tid)
                elif mod == PKG_NAME:
                    self.exported.add(sym)   # 二级再导出，尽力而为
            # `from . import storage` 形式：别名即子模块名
            for alias, target in p.mod_aliases.items():
                rel2 = self.modules.get(target)
                if rel2:
                    self.exported.add(f"{rel2}::<module>")
                self.exported.add(f"{PKG_NAME}/{alias}.py::<module>")
            # __all__ 里但不在 import 表中的名字（例如 "baselines"/"storage" 模块名）
            for nm in names:
                tid = f"{PKG_NAME}/{nm}.py::<module>"
                if tid in self.defs:
                    self.exported.add(tid)

    # ---------------------------------------------------------------- 连边

    def _module_of_rel(self, rel):
        return self.parsers[rel].module if rel in self.parsers else ""

    def _resolve_receiver_module(self, rel, name):
        """接收者名字 → 点分模块名（若是模块别名）。"""
        p = self.parsers.get(rel)
        if p and name in p.mod_aliases:
            target = p.mod_aliases[name]
            if target in self.modules:
                return target
            # `import _stats as S`：experiments/ 目录被 sys.path.insert 进
            # 搜索路径，故模块名只按末段匹配。同名末段多解时返回 None
            # （交给名字兜底，宁高估可达性）。
            tails = self.mod_tail.get(target.split(".")[-1])
            if tails and len(tails) == 1:
                return _dotted_module(next(iter(tails)))
            return None
        if p and name in p.sym_aliases:
            mod, sym = p.sym_aliases[name]
            # `from x import y`：y 本身是模块（`from metaphor_graph import baselines`）
            for cand in (f"{mod}.{sym}", f"{PKG_NAME}.{sym}", sym):
                if cand in self.modules:
                    return cand
            tails = self.mod_tail.get(sym)
            if tails and len(tails) == 1:
                return _dotted_module(next(iter(tails)))
            return None
        return None

    def _lookup_symbol(self, rel, name):
        """接收者名字 → 本项目内的定义 id（若是导入的符号）。"""
        p = self.parsers.get(rel)
        if not p:
            return None
        if name in p.sym_aliases:
            mod, sym = p.sym_aliases[name]
            rel2 = self.modules.get(mod)
            if rel2 and sym in self.by_file.get(rel2, {}):
                return self.by_file[rel2][sym]
            # sys.path hack（`import _stats as S` 之类）
            tails = self.mod_tail.get(mod.split(".")[-1])
            if tails and len(tails) == 1:
                r3 = next(iter(tails))
                if sym in self.by_file.get(r3, {}):
                    return self.by_file[r3][sym]
            # 包内再导出（__init__.py）
            if mod == PKG_NAME:
                for init_rel, pp in self.parsers.items():
                    if _is_pkg_init(init_rel) and init_rel.startswith(PKG_NAME + "/"):
                        if name in pp.sym_aliases:
                            m2, s2 = pp.sym_aliases[name]
                            r2 = self.modules.get(m2)
                            if r2 and s2 in self.by_file.get(r2, {}):
                                return self.by_file[r2][s2]
        return None

    def _class_of(self, nid):
        d = self.defs.get(nid)
        return d.enclosing_class if d else None

    def _methods_of_class(self, rel, cls_qual):
        out = []
        for q, nid in self.by_file.get(rel, {}).items():
            if q.startswith(cls_qual + "."):
                rest = q[len(cls_qual) + 1:]
                if "." not in rest:
                    out.append(nid)
        return out

    def _subclass_methods(self, rel, cls_qual, meth):
        """本项目内所有继承自该类的子类里的同名方法。"""
        out = []
        base_nid = f"{rel}::{cls_qual}"
        for nid, d in self.defs.items():
            if d.kind != "class" or not d.bases:
                continue
            if any(b == cls_qual or b.split(".")[-1] == cls_qual for b in d.bases):
                cand = f"{d.nid}.{meth}"
                if cand in self.defs:
                    out.append(cand)
        return out

    def _base_methods(self, rel, cls_qual, meth):
        """沿继承链找基类方法（同名）。"""
        out = []
        seen = set()
        stack = [f"{rel}::{cls_qual}"]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            d = self.defs.get(cur)
            if d is None:
                continue
            for b in d.bases:
                simple = b.split(".")[-1]
                for nid2, d2 in self.defs.items():
                    if d2.kind != "class" or d2.name != simple:
                        continue
                    cand = f"{d2.nid}.{meth}"
                    if cand in self.defs:
                        out.append(cand)
                    stack.append(d2.nid)
        return out

    def _find_class_nid(self, cls_name):
        """类名 → 类节点 id。多解（同名类）时返回 None，避免猜错。"""
        hits = [nid for nid in self.by_name.get(cls_name, [])
                if self.defs[nid].kind == "class"]
        if len(hits) == 1:
            return hits[0]
        # 同名多解：优先取与被调用点同文件的那个
        return None

    def _class_hint_for(self, site, recv):
        """尽力推断局部接收者的类：参数注解 > 赋值时的构造调用。

        只做单步、无分支的推断，宁可返回 None（走名字兜底）也不猜错。
        """
        owner = self.defs.get(site.owner)
        if owner is None or owner.kind == "class":
            return None
        node = owner.body_node
        # 1) 形参注解 `def f(x: MetaphorSHG)` / `-> ...`
        for a in list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs):
            if a.arg == recv and a.annotation is not None:
                ch = _annotation_class(a.annotation)
                if ch:
                    return ch
        # 2) 赋值 `x = Foo(...)` / `x: Foo = ...`
        for sub in ast.walk(node):
            targets = []
            if isinstance(sub, ast.Assign):
                targets = sub.targets
                value = sub.value
            elif isinstance(sub, ast.AnnAssign) and sub.value is not None:
                targets = [sub.target]
                value = sub.value
            else:
                continue
            if not any(isinstance(t, ast.Name) and t.id == recv for t in targets):
                continue
            if isinstance(value, ast.Call):
                f = value.func
                if isinstance(f, ast.Name):
                    return f.id
                if isinstance(f, ast.Attribute):
                    return f.attr
            if isinstance(value, ast.ListComp):
                return None
        # 3) 迭代：`for e in shg.edges` → e 的元素类未知，但 `for x in <Name>`
        #    无法定类，跳过（避免误判）
        return None

    def _receiver_is_project_method(self, attr):
        """项目内是否真有名为 attr 的方法（用于白名单两段式判定）。"""
        return attr in self.by_method_name

    def _resolve(self, site):
        """返回 (目标 nid 列表, 置信度)。"""
        chain = site.chain
        if not chain:
            return [], "low"
        rel = site.file
        if len(chain) == 1:
            name = chain[0]
            tgt = self._lookup_symbol(rel, name)
            if tgt:
                return [tgt], "high"
            if name in self.by_file.get(rel, {}):
                return [self.by_file[rel][name]], "high"
            # 星号导入
            p = self.parsers.get(rel)
            if p:
                for mod in p.star_modules:
                    rel2 = self.modules.get(mod)
                    if rel2 and name in self.by_file.get(rel2, {}):
                        return [self.by_file[rel2][name]], "high"
            if name in site.locals:
                # 局部变量/参数：可能是可调用注入 → 按名字全局兜底
                cand = [n for n in self.by_name.get(name, []) if n != site.owner]
                return cand, "low" if cand else "high"
            cand = [n for n in self.by_name.get(name, []) if n != site.owner]
            return cand, "low" if cand else "high"

        # 属性链 a.b(.c)
        recv, attr = chain[0], chain[-1]
        # `Foo().bar(...)` / `a.b().bar(...)`：接收者由**实例化表达式**给出，
        # 类名直接从 AST 拿到（比注解推断更可靠）。
        if site.cls_hint and len(chain) >= 2 and site.cls_hint != recv:
            cls_nid = self._find_class_nid(site.cls_hint)
            if cls_nid:
                cand = f"{cls_nid}.{attr}"
                if cand in self.defs:
                    return [cand], "high"
                out = [n for n in self.by_method_name.get(attr, [])
                       if n.startswith(cls_nid + ".")]
                if out:
                    return out, "high"
        if recv in ("self", "cls"):
            d = self.defs.get(site.owner)
            cls_qual = d.enclosing_class if d else None
            if cls_qual:
                cand = f"{rel}::{cls_qual}.{attr}"
                if cand in self.defs:
                    out = [cand]
                    out += self._subclass_methods(rel, cls_qual, attr)
                    return out, "high"
                out = self._base_methods(rel, cls_qual, attr)
                if out:
                    return out, "high"
                out = [c for c in self._methods_of_class(rel, cls_qual)
                       if self.defs[c].name == attr]
                if out:
                    return out, "high"
        if recv == "super":
            d = self.defs.get(site.owner)
            cls_qual = d.enclosing_class if d else None
            if cls_qual:
                out = self._base_methods(rel, cls_qual, attr)
                if out:
                    return out, "high"

        # 接收者是模块（`mod.foo` / `_emb.foo`）
        mod = self._resolve_receiver_module(rel, recv)
        if mod:
            rel2 = self.modules.get(mod)
            if rel2:
                if attr in self.by_file.get(rel2, {}):
                    return [self.by_file[rel2][attr]], "high"
                out = [n for n in self.by_name.get(attr, [])
                       if self.defs[n].file == rel2]
                if out:
                    return out, "high"

        # 接收者是导入的类/函数（`MetaphorSHG.from_json(...)` / `os.path` 之类）
        sym = self._lookup_symbol(rel, recv)
        if sym:
            direct = f"{sym}.{attr}"
            if direct in self.defs:
                return [direct], "high"
            # 类方法 / 静态方法：从类节点往下找
            out = [n for n in self.by_method_name.get(attr, [])
                   if n.startswith(sym + ".")]
            if out:
                return out, "high"
            # 接收者是个对象常量（如 BASELINES）→ 同模块方法兜底
            out = [n for n in self.by_name.get(attr, [])
                   if self.defs[n].file == rel and n != site.owner]
            if out:
                return out, "high"

        # 接收者是本模块的模块级名字（函数/常量/类）
        if recv in self.by_file.get(rel, {}):
            out = [n for n in self.by_name.get(attr, [])
                   if self.defs[n].file == rel and n != site.owner]
            if out:
                return out, "high"

        # 局部变量：先试注解/赋值推断出的类
        if recv in site.locals:
            hint = self._class_hint_for(site, recv)
            if hint:
                cls_nid = self._find_class_nid(hint)
                if cls_nid:
                    cand = f"{cls_nid}.{attr}"
                    if cand in self.defs:
                        return [cand], "high"

        # 兜底：按方法名全局连边（保守 —— 宁可高估可达性）
        if attr in _BUILTIN_METHOD_NAMES and not self._receiver_is_project_method(attr):
            # 纯标准库惯用名且项目内无同名方法 → 不连边
            # （否则 `s.encode("utf-8")` 会把 MetaphorHGNN.encode 误判为已调用）
            return [], "high"
        same_file = [n for n in self.by_method_name.get(attr, [])
                     if self.defs[n].file == rel and n != site.owner]
        out = same_file or [n for n in self.by_method_name.get(attr, [])
                            if n != site.owner]
        return out, ("low" if out else "high")

    def _build_edges(self):
        # 模块顶层（含 `if __name__ == "__main__"` 块）的调用点挂到虚拟根节点。
        # `_ModuleParser` 里 owner="" 同时覆盖这两种情况，因为它们都在 tree.body。
        for rel, p in self.parsers.items():
            top = f"{rel}::<toplevel>"
            for site in p.sites:
                owner = site.owner or top
                if owner != top and owner not in self.defs:
                    continue
                targets, conf = self._resolve(site)
                for t in targets:
                    if t == owner:
                        continue
                    self.edges[owner].add(t)
                    key = (owner, t)
                    if self.edge_conf.get(key) != "high":
                        self.edge_conf[key] = conf
                if not targets and site.is_call:
                    self.unresolved_calls[site.chain[-1] if site.chain else "?"] += 1

    def _count_call_sites(self):
        for rel, p in self.parsers.items():
            for site in p.sites:
                if not site.is_call or not site.chain:
                    continue
                targets, _ = self._resolve(site)
                for t in targets:
                    if t in self.defs:
                        self.defs[t].call_site_count += 1

    # ---------------------------------------------------------------- 可达性

    def _bfs(self, root_kinds, high_only=False):
        """从根节点 BFS。``high_only=True`` 只走精确解析的边。

        可达性判定用**全图**（含低置信兜底边，保守）；调用链展示优先用
        **高置信子图** —— 否则代表性路径会变成
        `A::main → 无关模块::foo → ...` 这种由名字兜底边串起来的假链。
        """
        dist = {}
        pred = {}
        dq = deque()
        for k in root_kinds:
            for r in sorted(self.roots.get(k, ())):
                if r in dist:
                    continue
                dist[r] = 0
                pred[r] = None
                dq.append(r)
        while dq:
            cur = dq.popleft()
            for nxt in sorted(self.edges.get(cur, ())):
                if nxt in dist:
                    continue
                if high_only and self.edge_conf.get((cur, nxt), "high") != "high":
                    continue
                dist[nxt] = dist[cur] + 1
                pred[nxt] = cur
                dq.append(nxt)
        return dist, pred

    def _path(self, nid, pred):
        out = []
        cur = nid
        guard = 0
        while cur is not None and guard < 64:
            out.append(cur)
            cur = pred.get(cur)
            guard += 1
        out.reverse()
        return out

    def _path_conf(self, path):
        for a, b in zip(path, path[1:]):
            if self.edge_conf.get((a, b), "high") == "low":
                return "low"
        return "high"

    # ---------------------------------------------------------------- 参数

    def _find_unused_params(self):
        for nid, d in self.defs.items():
            if d.kind == "class":
                continue
            node = d.body_node
            d.loop_if_ids = frozenset(_collect_loop_ifs(node))
            used = set()
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                    used.add(sub.id)
            d.unused_params = [p for p in d.params
                               if p not in ("self", "cls") and p not in used]
            # 存根 / 抽象方法 / Protocol 接口不算「参数被忽略」
            # （body 为 `...` / `pass` / `raise NotImplementedError` / 纯 docstring）
            body = [s for s in node.body
                    if not (isinstance(s, ast.Expr) and
                            isinstance(s.value, ast.Constant) and
                            (s.value.value is Ellipsis or
                             isinstance(s.value.value, str)))]
            if not body:
                d.unused_params = []
            elif len(body) == 1 and isinstance(body[0], (ast.Pass, ast.Raise)):
                d.unused_params = []
            if any(x in ("abstractmethod", "overload", "runtime_checkable")
                   for x in d.decorators):
                d.unused_params = []
            # 接口协议方法：所在类以 Protocol / ABC 为基类
            if d.enclosing_class:
                cls = self.defs.get(f"{d.file}::{d.enclosing_class}")
                if cls and any(b.split(".")[-1] in ("Protocol", "ABC", "ABCMeta")
                               for b in cls.bases):
                    d.unused_params = []

    # ---------------------------------------------------------------- 汇总

    def result(self):
        self.scan()
        dist_all, pred_all = self._bfs(("prod_internal", "prod_external", "test"))
        dist_int, pred_int = self._bfs(("prod_internal",))
        dist_ext, pred_ext = self._bfs(("prod_external",))
        dist_test, pred_test = self._bfs(("test",))

        nodes = []
        summary = defaultdict(int)
        for nid, d in sorted(self.defs.items()):
            if not d.is_public:
                continue
            reachable = nid in dist_all
            from_int = nid in dist_int
            from_ext = nid in dist_ext
            from_test = nid in dist_test
            exported = nid in self.exported
            if from_int or from_ext:
                cls = "生产路径"
                root_kind = "prod_internal" if from_int else "prod_external"
                pred = pred_int if from_int else pred_ext
                p = self._path(nid, pred)
            elif from_test:
                cls = "仅测试"
                root_kind = "test"
                p = self._path(nid, pred_test)
            elif exported:
                cls = "仅导出"
                root_kind = None
                p = []
            else:
                cls = "孤立"
                root_kind = None
                p = []
            if cls in ("孤立", "仅导出"):
                conf = "high" if d.call_site_count == 0 else "medium"
            else:
                conf = self._path_conf(p) if p else "high"
            summary[cls] += 1
            nodes.append({
                "id": nid,
                "module": d.module,
                "file": d.file,
                "qualname": d.qualname,
                "name": d.name,
                "kind": d.kind,
                "line": d.lineno,
                "has_doc": d.has_doc,
                "public": d.is_public,
                "classification": cls,
                "reachable": reachable,
                "reach_from": root_kind,
                "external_only": bool(from_ext and not from_int),
                "test_reachable": from_test,
                "exported": exported,
                "call_site_count": d.call_site_count,
                "shortest_path": p,
                "path_len": (len(p) - 1) if p else None,
                "confidence": conf,
                "unused_params": d.unused_params,
            })

        patterns = self._patterns()
        return {
            "meta": {
                "package": PKG_NAME,
                "scanned_files": len(self.files),
                "scanned_defs_total": len(self.defs),
                "audited_public_defs": len(nodes),
                "parse_errors": self.errors,
                "root_counts": {k: len(v) for k, v in self.roots.items()},
            },
            "entry_points": {k: sorted(v) for k, v in self.roots.items()},
            "summary": dict(summary),
            "nodes": nodes,
            "patterns": patterns,
            "limitations": _LIMITATIONS,
        }

    # ---------------------------------------------------------------- 可疑模式

    def _patterns(self):
        gates, fallbacks, unused_pub = [], [], []
        for nid, d in sorted(self.defs.items()):
            if d.kind == "class":
                continue
            if not d.in_pkg or d.in_test_file:
                continue
            if d.file in PATTERN_SKIP_FILES:
                # 审计工具自身的元代码：逐条自报纯属噪声
                continue
            node = d.body_node
            for sub in ast.walk(node):
                if isinstance(sub, ast.If):
                    g = _gate_of(sub, d, self)
                    if g:
                        gates.append(g)
                    f = _fallback_of_guard(sub, d, self)
                    if f:
                        fallbacks.append(f)
                if isinstance(sub, ast.ExceptHandler):
                    f = _fallback_of_except(sub, d, self)
                    if f:
                        fallbacks.append(f)
            if d.is_public and d.has_doc and d.call_site_count == 0 \
                    and not _is_property_like(d):
                unused_pub.append({
                    "id": nid, "file": d.file, "line": d.lineno,
                    "name": d.name, "kind": d.kind,
                    "classification": None,
                })
        gates.sort(key=lambda x: (x["file"], x["line"]))
        fallbacks.sort(key=lambda x: (x["file"], x["line"]))
        unused_pub.sort(key=lambda x: (x["file"], x["line"]))
        cls_by_id = {n["id"]: n["classification"]
                     for n in getattr(self, "result_nodes_cache", [])}
        for u in unused_pub:
            u["classification"] = cls_by_id.get(u["id"], "?")
        unused_params = [
            {"id": n["id"], "file": n["file"], "line": n["line"],
             "name": n["name"], "params": n["unused_params"],
             "classification": n["classification"]}
            for n in getattr(self, "result_nodes_cache", [])
            if n["unused_params"] and n["file"] not in PATTERN_SKIP_FILES
        ]
        unused_params.sort(key=lambda x: (x["file"], x["line"]))
        return {
            "hardcoded_gate": gates,
            "hardcoded_gate_review": [g for g in gates if g["risk"] == "review"],
            "silent_fallback": fallbacks,
            "unused_public_docstring": unused_pub,
            "unused_param": unused_params,
        }


def _attr_chain_ok(chain):
    return bool(chain)


def _annotation_class(node):
    """从注解表达式里取类名：``MetaphorSHG`` / ``List[MetaphorHyperedge]`` → 后者取内层。"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        # Optional[X] / List[X] / Dict[K, V] → 取第一个类名参数
        inner = node.slice
        if isinstance(inner, ast.Tuple) and inner.elts:
            for e in inner.elts:
                c = _annotation_class(e)
                if c:
                    return c
        return _annotation_class(inner)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            return _annotation_class(ast.parse(node.value, mode="eval").body)
        except SyntaxError:
            return None
    return None


# ------------------------------------------------------------------- 模式判定


def _literal_collection(node):
    """节点是否是全常量集合/列表/元组 → 返回字面量列表，否则 None。"""
    if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        if not node.elts:
            return None
        out = []
        for e in node.elts:
            if not isinstance(e, ast.Constant):
                return None
            out.append(repr(e.value))
        return out
    if isinstance(node, ast.Dict):
        return None
    return None


def _module_const_collection(name, d, audit):
    """名字是否在模块级绑定到全常量集合/列表/元组/字典。"""
    rel = d.file
    tree = audit.trees.get(rel)
    if tree is None:
        return None
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        else:
            continue
        if value is None:
            continue
        for t in targets:
            if isinstance(t, ast.Name) and t.id == name:
                lit = _literal_collection(value)
                if lit:
                    return lit
                if isinstance(value, ast.Dict):
                    keys = [k for k in value.keys if isinstance(k, ast.Constant)]
                    if keys and len(keys) == len(value.keys):
                        return [repr(k.value) for k in keys]
    return None


def _gate_test_atoms(test):
    """把 if 条件拆成原子比较。"""
    out = []
    if isinstance(test, ast.BoolOp):
        for v in test.values:
            out.extend(_gate_test_atoms(v))
    elif isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        out.extend(_gate_test_atoms(test.operand))
    elif isinstance(test, ast.Compare):
        out.append(test)
    return out


def _gate_of(if_node, d, audit):
    """硬编码门控：字面量集合/字面量比较 且 分支体是「跳过工作」。

    风险分级（``risk``）：
      ``review`` 分支跳过**整个函数/整个循环之外**的工作 —— 这类门控一旦字面量
                 与数据脱节，就会静默关闭整条通道（mipvu 的历史缺陷形态）；
      ``low``    分支体在循环内逐项 continue，或字面量来自带 STOP/SKIP/WORD
                 等语义提示的模块常量（词表/噪声表/CLI 分支）—— 正常实现。
    """
    skips = _skip_stmts(if_node.body) or _skip_stmts(if_node.orelse)
    if not skips:
        return None
    in_loop = id(if_node) in d.loop_if_ids
    hits = []
    for cmp in _gate_test_atoms(if_node.test):
        for op, comp in zip(cmp.ops, cmp.comparators):
            if isinstance(op, (ast.In, ast.NotIn)):
                lit = _literal_collection(comp)
                if lit:
                    hits.append(("内联字面集合", lit))
                    continue
                if isinstance(comp, ast.Name):
                    lit = _module_const_collection(comp.id, d, audit)
                    if lit:
                        hits.append((f"模块常量集合 {comp.id}", lit))
            if isinstance(op, (ast.Eq, ast.NotEq)):
                for side, other in ((comp, cmp.left), (cmp.left, comp)):
                    if isinstance(side, ast.Constant) and isinstance(side.value, str) \
                            and isinstance(other, (ast.Name, ast.Attribute)):
                        hits.append(("字面量相等", [repr(side.value)]))
    if not hits:
        return None
    kinds = {k for k, _ in hits}
    const_names = [k for k in kinds if k.startswith("模块常量集合")]
    risky = not in_loop
    if const_names and all(
            any(h in nm.upper() for h in _LOW_RISK_CONST_HINTS) for nm in const_names):
        risky = False
    # 纯数值字面量集合（`lab in (0, 1, 2)`）是标签域校验，不是通道门控
    all_lits = [x for _, vals in hits for x in vals]
    if all_lits and all(_is_number_literal(x) for x in all_lits):
        risky = False
    lits = sorted(set(all_lits))
    if len(lits) > 12:
        lits = lits[:12] + [f"…(+{len(lits) - 12})"]
    return {
        "id": d.nid,
        "file": d.file,
        "line": if_node.lineno,
        "function": d.qualname,
        "kinds": sorted(kinds),
        "literals": lits,
        "risk": "review" if risky else "low",
        "in_loop": in_loop,
        "public": d.is_public,
    }


def _is_number_literal(text):
    try:
        float(text.strip("'\""))
        return True
    except (ValueError, AttributeError):
        return False


def _is_property_like(d):
    """``@property`` / ``@cached_property`` 等方法靠属性访问调用，不算零调用点。"""
    return any(x in ("property", "cached_property", "staticmethod", "classmethod")
               for x in d.decorators)


def _fallback_of_except(handler, d, audit):
    """静默回落：except 体无 raise/日志，把错误变成「正常返回」。

    只报两类真正危险的形态：
      * ``except ...: pass`` / ``continue`` / ``break`` —— 空吞；
      * ``except ...: return <空值>`` —— 把失败伪装成「无结果」。
    其余「except 里做赋值后继续」的形态不报（多半有下游检查），
    以免噪声淹没真信号。
    """
    body = handler.body
    if _has_raise_or_log(body):
        return None
    exc = "bare except"
    if handler.type is not None:
        exc = ast.unparse(handler.type)
    if all(isinstance(s, (ast.Pass, ast.Continue, ast.Break)) for s in body):
        kind = "except 空吞"
    elif len(body) == 1 and isinstance(body[0], ast.Return) and _empty_value(body[0].value):
        kind = "except 返回空值"
    else:
        return None
    return {
        "id": d.nid, "file": d.file, "line": handler.lineno,
        "function": d.qualname, "kind": kind, "exception": exc,
        "public": d.is_public,
    }


def _is_negative_existence(test):
    """``not x`` / ``x is None`` / ``not x.attr`` —— 但排除类型断言谓词。

    ``if not isinstance(node, ast.If): return None`` 是**输入类型分派**，
    不是降级回落，必须排除（否则每个 AST 工具函数都自报一遍）。
    """
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        v = test.operand
        if isinstance(v, ast.Call):
            f = v.func
            nm = f.attr if isinstance(f, ast.Attribute) else (
                f.id if isinstance(f, ast.Name) else None)
            if nm in _TYPE_PREDICATES:
                return False
            return True
        if isinstance(v, (ast.Name, ast.Attribute)):
            return True
        if isinstance(v, ast.BoolOp):
            return True
        return False
    if isinstance(test, ast.Compare) and len(test.ops) == 1:
        if isinstance(test.ops[0], (ast.Is, ast.IsNot)):
            for side in (test.left, test.comparators[0]):
                if isinstance(side, ast.Constant) and side.value is None:
                    return True
    return False


def _is_trivial_guard(if_node):
    """``if not x: continue`` 形式的**循环内过滤** —— 逐项跳过，不是降级通道。

    判据：条件只涉及一个名字/属性，且分支体只是 continue/break（无 return），
    且该 If 位于某个循环体内（其祖先里有 For/While/While-comp）。
    这类守卫是正常的数据清洗，报出来只会淹没真信号。
    """
    if not _is_negative_existence(if_node.test):
        return False
    if not if_node.body or len(if_node.body) > 2:
        return False
    if not all(isinstance(s, (ast.Continue, ast.Break)) for s in if_node.body):
        return False
    v = if_node.test.operand if isinstance(if_node.test, ast.UnaryOp) else None
    if v is not None and not isinstance(v, (ast.Name, ast.Attribute)):
        return False
    return True


def _fallback_of_guard(if_node, d, audit):
    """降级返回：``if not key: return <空值>`` / ``if x is None: return []``。

    只报**函数级**的降级出口（return 空值），这是 evaluate_real 那类
    「静默产出看似正常的结果」缺陷的形态。循环内的逐项 continue 过滤不报
    （见 ``_is_trivial_guard``）。
    """
    if not _is_negative_existence(if_node.test):
        return None
    body = if_node.body
    if len(body) != 1 or not isinstance(body[0], ast.Return):
        return None
    if not _empty_value(body[0].value):
        return None
    if _is_trivial_guard(if_node):
        return None
    return {"id": d.nid, "file": d.file, "line": if_node.lineno,
            "function": d.qualname, "kind": "guard 返回空值",
            "exception": ast.unparse(if_node.test)[:70], "public": d.is_public,
            "returns": ast.unparse(body[0].value)[:30] if body[0].value else "None"}


_LIMITATIONS = [
    "不执行被审代码：所有结论来自 AST，运行期动态派发（getattr(obj, name)、"
    "注册表字典、插件式回调、装饰器改写）一律看不见。",
    "接收者不可解析的方法调用按方法名全局兜底连边（置信 low）；"
    "但若方法名在 _BUILTIN_METHOD_NAMES 白名单内（encode/get/append/…）则**不**兜底，"
    "这类同名项目方法可能被漏报为不可达 —— 这是本审计主要的假阴性来源。",
    "测试文件的全部定义都被当作根（含测试辅助函数），因此「仅测试」是上界估计。",
    "每个模块的顶层语句都被当作入口（导入即执行），因此模块级调用链会把"
    "仅被顶层执行一次的代码判为可达。",
    "不区分「可达」与「在关键路径上生效」：例如 hgnn 的跨层传播只要被"
    "任何非测试调用方调用过就算可达，即使检索打分路径并不走它。"
    "要判后者需要运行期插桩（覆盖率 / 调用计数），不在本脚本能力范围内。",
    "硬编码门控只认「字面量集合 / 字符串字面量比较」且分支体为跳过；"
    "数值阈值门控（if x < 0.6）、以及「硬编码 id 写在模块常量里再被 .get() 查表」"
    "的间接形态不会被完整捕获。",
    "参数被忽略只做名字级检查：通过 globals()/locals()/**kwargs 间接使用形参"
    "会被误报为未使用。",
    "跨仓库调用（本项目之外的调用方、外部文档/脚本）不在扫描范围。",
]


# =========================================================================== 报告


def _fmt_path(path, audit, limit=6):
    if not path:
        return "(无)"
    def short(nid):
        if nid.endswith(">"):
            return nid.split("::")[0] + "::" + nid.split("::")[1]
        d = audit.defs.get(nid)
        if d is None:
            return nid
        return f"{os.path.basename(d.file)}::{d.qualname}"
    parts = [short(n) for n in path]
    if len(parts) > limit:
        parts = parts[:limit - 1] + ["…"] + parts[-1:]
    return " → ".join(parts)


def render_text(res, audit, section="all"):
    L = []
    ap = L.append
    meta, summ = res["meta"], res["summary"]
    ap("=" * 84)
    ap("静态可达性审计 —— metaphor_graph 包（谁被调用 / 调用链 / 死代码 / 可疑模式）")
    ap("=" * 84)
    ap(f"扫描文件 {meta['scanned_files']} 个；定义 {meta['scanned_defs_total']} 个；"
       f"其中公开定义 {meta['audited_public_defs']} 个")
    ap(f"入口点：prod_internal {meta['root_counts'].get('prod_internal', 0)} / "
       f"prod_external {meta['root_counts'].get('prod_external', 0)} / "
       f"test {meta['root_counts'].get('test', 0)}")
    if meta["parse_errors"]:
        ap(f"⚠️ 解析失败 {len(meta['parse_errors'])} 个文件：{meta['parse_errors'][:3]}")
    ap("")
    ap("-" * 84)
    ap("【一】分类计数")
    ap("-" * 84)
    for k in ("生产路径", "仅测试", "仅导出", "孤立"):
        ap(f"  {k:<6} {summ.get(k, 0):>5}")
    ap(f"  {'合计':<6} {sum(summ.values()):>5}")
    ext_only = [n for n in res["nodes"] if n["external_only"]]
    ap(f"  其中「生产路径」但仅由 experiments//release/ 等外部脚本可达：{len(ext_only)}")
    ap("")

    if section in ("all", "dead"):
        ap("-" * 84)
        ap("【二】死代码：全部「孤立」（无任何入口可达，含测试与导出）")
        ap("-" * 84)
        dead = [n for n in res["nodes"] if n["classification"] == "孤立"]
        if not dead:
            ap("  （无）")
        for n in dead:
            ap(f"  {n['file']}:{n['line']}  {n['qualname']}  "
               f"[{n['kind']}, 置信 {n['confidence']}]"
               f"{'  (有 docstring)' if n['has_doc'] else ''}")
        ap(f"  —— 共 {len(dead)} 个")
        ap("")
        ap("-" * 84)
        ap("【三】死代码：全部「仅导出」（__init__.py 导出但无任何调用点）")
        ap("-" * 84)
        exp = [n for n in res["nodes"] if n["classification"] == "仅导出"]
        if not exp:
            ap("  （无）")
        for n in exp:
            ap(f"  {n['file']}:{n['line']}  {n['qualname']}  [{n['kind']}]")
        ap(f"  —— 共 {len(exp)} 个")
        ap("")

    if section in ("all", "dead"):
        ap("-" * 84)
        ap("【四】「仅测试」可达（生产路径上无调用点，只有测试覆盖）")
        ap("-" * 84)
        t = [n for n in res["nodes"] if n["classification"] == "仅测试"]
        for n in sorted(t, key=lambda x: (x["file"], x["line"])):
            ap(f"  {n['file']}:{n['line']}  {n['qualname']}  [{n['kind']}]")
        ap(f"  —— 共 {len(t)} 个")
        ap("")

    if section in ("all", "paths"):
        ap("-" * 84)
        ap("【五】代表调用链（抽样：每个模块最深/最浅各一条）")
        ap("-" * 84)
        shown = 0
        for n in sorted(res["nodes"], key=lambda x: (x["file"], x["line"])):
            if n["classification"] != "生产路径" or not n["shortest_path"]:
                continue
            if n["path_len"] and n["path_len"] >= 3 and shown < 18:
                ap(f"  {n['qualname']} (len={n['path_len']}, 置信 {n['confidence']})")
                ap(f"      {_fmt_path(n['shortest_path'], audit)}")
                shown += 1
        ap("")

    if section in ("all", "patterns"):
        p = res["patterns"]
        ap("-" * 84)
        ap("【六】可疑模式 ①：硬编码门控（字面量集合/字面量比较 + 分支跳过工作）")
        ap("-" * 84)
        ap("  判定：if 条件里出现 `x in {字面量集合}` / `x == \"字面量\"`，")
        ap("        且该分支体是 continue/break/pass/return 空值 —— 即该门控能**静默**")
        ap("        丢弃工作。mipvu 的历史缺陷（写死 6 个级联 id）属于此类。")
        ap("  分级：review = 分支跳过整个函数/循环外的工作（可疑，需人工判断）；")
        ap("        low    = 循环内逐项过滤 / 词表常量 / 纯数字标签域校验（正常）。")
        ap("")
        for g in p["hardcoded_gate_review"]:
            ap(f"  ⚠️[review] {g['file']}:{g['line']}  {g['function']}  "
               f"[{'+'.join(g['kinds'])}]")
            ap(f"      字面量：{', '.join(g['literals'][:12])}")
        low = [g for g in p["hardcoded_gate"] if g["risk"] == "low"]
        if low:
            ap("")
            ap(f"  ——[low] 以下 {len(low)} 处为正常实现（循环内过滤 / 词表 / 标签域）：")
            for g in low:
                ap(f"      {g['file']}:{g['line']}  {g['function']}  "
                   f"[{'+'.join(g['kinds'])}]  {', '.join(g['literals'][:6])}")
        ap("")
        ap(f"  —— 共 {len(p['hardcoded_gate'])} 处（其中 review "
           f"{len(p['hardcoded_gate_review'])} 处 / low {len(low)} 处）")
        ap("")
        ap("-" * 84)
        ap("【七】可疑模式 ②：静默回落（吞异常 / 无日志降级）")
        ap("-" * 84)
        ap("  判定：except 体只有 pass/continue/break 或 return 空值，且无 raise/日志；")
        ap("        或函数级 `if not <数据>: return <空值>`。evaluate_real 的")
        ap("        假性 P1=0.434 属于前者（静默换后端，仍打印看似正常的指标）。")
        ap("")
        for f in p["silent_fallback"]:
            ap(f"  {f['file']}:{f['line']}  {f['function']}  [{f['kind']}]"
               f"  ({f['exception']})")
        ap(f"  —— 共 {len(p['silent_fallback'])} 处")
        ap("")
        ap("-" * 84)
        ap("【八】可疑模式 ③：有 docstring 但零调用点的公开函数")
        ap("-" * 84)
        for u in p["unused_public_docstring"]:
            ap(f"  {u['file']}:{u['line']}  {u['name']}  [{u['kind']}, {u['classification']}]")
        ap(f"  —— 共 {len(p['unused_public_docstring'])} 个")
        ap("")
        ap("-" * 84)
        ap("【九】可疑模式 ④：参数被忽略（声明了但函数体内未引用）")
        ap("-" * 84)
        ap("  注：不做类型检查，只做名字级引用检查。回调签名占位（`**kw`）、")
        ap("      `_` 前缀约定参数属正常；`**kwargs` 转发场景无法静态判定。")
        ap("")
        for u in p["unused_param"]:
            ap(f"  {u['file']}:{u['line']}  {u['name']}({', '.join(u['params'])})"
               f"  [{u['classification']}]")
        ap(f"  —— 共 {len(p['unused_param'])} 个")
        ap("")

    ap("-" * 84)
    ap("【十】分析器能力边界（必读）")
    ap("-" * 84)
    for i, s in enumerate(res["limitations"], 1):
        ap(f"  {i}. {s}")
    ap("")
    ap("=" * 84)
    return "\n".join(L)


# =========================================================================== 入口


def audit(root_dir=None):
    """跑一次完整审计，返回结果字典（供测试/程序调用）。"""
    a = ReachabilityAudit(root_dir)
    a.scan()
    res = a.result()
    # 参数模式需要 nodes 视图，补齐后重算
    a.result_nodes_cache = res["nodes"]
    res["patterns"] = a._patterns()
    return res, a


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="静态可达性审计：谁被调用 / 调用链 / 死代码 / 可疑模式")
    ap.add_argument("--json", nargs="?", const="-", default=None,
                    metavar="PATH", help="输出 JSON（省略 PATH 则打到 stdout）")
    ap.add_argument("--section", default="all",
                    choices=("all", "dead", "patterns", "paths"),
                    help="只打印某一部分")
    args = ap.parse_args(argv)

    res, a = audit()
    if args.json:
        payload = json.dumps(res, ensure_ascii=False, indent=1)
        if args.json == "-":
            if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
                try:
                    sys.stdout.reconfigure(encoding="utf-8")
                except Exception:
                    pass
            print(payload)
        else:
            with open(args.json, "w", encoding="utf-8") as f:
                f.write(payload)
            print(f"已写入 {args.json}")
        return 0

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(render_text(res, a, args.section))
    return 0


if __name__ == "__main__":
    sys.exit(main())

# 首次远程 CI 失败

代码提交：e9a840246cb2f682e66520d9c81f310739b62d08。
运行：https://github.com/surface-user/StudyWorkbench/actions/runs/39937659602
desktop job：120361060166；backend job 通过。

desktop：依赖解析、格式、静态检查、2 项 Flutter 测试均通过；Windows release 编译失败，整轮 conclusion=failure。

关键原始错误（2026-10-23T10:19:42Z）：

```text
C:\Program Files\Microsoft Visual Studio\18\Enterprise\VC\Tools\MSVC\14.51.36231\include\experimental\coroutine(37,1): error C2338: static assertion failed: 'error STL1011: The /await compiler option, <experimental/coroutine>, <experimental/generator>, and <experimental/resumable> are deprecated by Microsoft and will be REMOVED SOON. They are superseded by the C++20 <coroutine> and C++23 <generator> headers.'
flutter_inappwebview_windows_plugin.vcxproj
Build process failed.
Process completed with exit code 1.
```

windows-latest 漂移到 VS18，插件 0.6.0 的旧协程依赖与其不兼容。本地 VS2022 17.14 构建通过。修正：仅将 desktop runner 固定 windows-2022，与实际验证工具链一致；不添加关闭编译错误的宏、不修改插件缓存、不删测试。VS18 兼容保留为依赖升级风险。

此前依据进入 post-job cleanup 而判断编译通过的进度表述无效，已明确更正；只有完成后的 job/run conclusion 才能判 CI 通过。

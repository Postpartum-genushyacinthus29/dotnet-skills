using ManagedCode.DotnetSkills.Runtime;

namespace ManagedCode.DotnetSkills.Tests;

public sealed class AgentInstallTargetTests
{
    [Theory]
    [MemberData(nameof(ProjectCases))]
    public void ResolveAllDetectedProject_UsesOnlyNativeAgentRoots(
        bool hasCodex,
        bool hasClaude,
        bool hasCopilot,
        bool hasGemini,
        bool hasJunie,
        bool hasSharedFallback)
    {
        using var tempDirectory = new TemporaryDirectory();
        CreatePlatformDirectories(tempDirectory.Path, hasCodex, hasClaude, hasCopilot, hasGemini, hasJunie, hasSharedFallback);

        var layouts = AgentInstallTarget.ResolveAllDetected(tempDirectory.Path, InstallScope.Project);
        var expected = BuildExpectedProjectLayouts(tempDirectory.Path, hasCodex, hasClaude, hasCopilot, hasGemini, hasJunie);

        Assert.Equal(expected.Select(item => item.Platform).ToArray(), layouts.Select(layout => layout.Agent).ToArray());
        Assert.Equal(expected.Select(item => item.Path).ToArray(), layouts.Select(layout => layout.PrimaryRoot.FullName).ToArray());
        Assert.Equal(expected.Select(item => item.Mode).ToArray(), layouts.Select(layout => layout.Mode).ToArray());
    }

    [Theory]
    [MemberData(nameof(ProjectCases))]
    public void ResolveAutoProject_SelectsFirstNativeRootOrThrows(
        bool hasCodex,
        bool hasClaude,
        bool hasCopilot,
        bool hasGemini,
        bool hasJunie,
        bool hasSharedFallback)
    {
        using var tempDirectory = new TemporaryDirectory();
        CreatePlatformDirectories(tempDirectory.Path, hasCodex, hasClaude, hasCopilot, hasGemini, hasJunie, hasSharedFallback);

        var expected = BuildExpectedProjectLayouts(tempDirectory.Path, hasCodex, hasClaude, hasCopilot, hasGemini, hasJunie);
        if (expected.Count == 0)
        {
            var exception = Assert.Throws<InvalidOperationException>(() =>
                AgentInstallTarget.Resolve(
                    explicitTargetPath: null,
                    agent: AgentPlatform.Auto,
                    scope: InstallScope.Project,
                    projectDirectory: tempDirectory.Path));

            Assert.Equal("No native agent platform detected for project scope. Create a native agent directory first or specify --agent/--target.", exception.Message);
            return;
        }

        var layout = AgentInstallTarget.Resolve(
            explicitTargetPath: null,
            agent: AgentPlatform.Auto,
            scope: InstallScope.Project,
            projectDirectory: tempDirectory.Path);

        Assert.Equal(expected[0].Platform, layout.Agent);
        Assert.Equal(expected[0].Path, layout.PrimaryRoot.FullName);
        Assert.Equal(expected[0].Mode, layout.Mode);
    }

    [Theory]
    [MemberData(nameof(GlobalCases))]
    public void ResolveAllDetectedGlobal_UsesOnlyNativeAgentRoots(
        bool hasCodex,
        bool hasClaude,
        bool hasCopilot,
        bool hasGemini,
        bool hasJunie,
        bool hasSharedFallback)
    {
        using var tempHome = new TemporaryDirectory();

        lock (TestEnvironmentLocks.UserProfile)
        {
            var previousHome = SetEnvironment("HOME", tempHome.Path);
            var previousUserProfile = SetEnvironment("USERPROFILE", tempHome.Path);
            var previousCodexHome = SetEnvironment("CODEX_HOME", null);

            try
            {
                CreatePlatformDirectories(tempHome.Path, hasCodex, hasClaude, hasCopilot, hasGemini, hasJunie, hasSharedFallback);

                var layouts = AgentInstallTarget.ResolveAllDetected(tempHome.Path, InstallScope.Global);
                var expected = BuildExpectedGlobalLayouts(tempHome.Path, hasCodex, hasClaude, hasCopilot, hasGemini, hasJunie);

                Assert.Equal(expected.Select(item => item.Platform).ToArray(), layouts.Select(layout => layout.Agent).ToArray());
                Assert.Equal(expected.Select(item => item.Path).ToArray(), layouts.Select(layout => layout.PrimaryRoot.FullName).ToArray());
                Assert.Equal(expected.Select(item => item.Mode).ToArray(), layouts.Select(layout => layout.Mode).ToArray());
            }
            finally
            {
                SetEnvironment("HOME", previousHome);
                SetEnvironment("USERPROFILE", previousUserProfile);
                SetEnvironment("CODEX_HOME", previousCodexHome);
            }
        }
    }

    [Theory]
    [MemberData(nameof(GlobalCases))]
    public void ResolveAutoGlobal_SelectsFirstNativeRootOrThrows(
        bool hasCodex,
        bool hasClaude,
        bool hasCopilot,
        bool hasGemini,
        bool hasJunie,
        bool hasSharedFallback)
    {
        using var tempHome = new TemporaryDirectory();

        lock (TestEnvironmentLocks.UserProfile)
        {
            var previousHome = SetEnvironment("HOME", tempHome.Path);
            var previousUserProfile = SetEnvironment("USERPROFILE", tempHome.Path);
            var previousCodexHome = SetEnvironment("CODEX_HOME", null);

            try
            {
                CreatePlatformDirectories(tempHome.Path, hasCodex, hasClaude, hasCopilot, hasGemini, hasJunie, hasSharedFallback);

                var expected = BuildExpectedGlobalLayouts(tempHome.Path, hasCodex, hasClaude, hasCopilot, hasGemini, hasJunie);
                if (expected.Count == 0)
                {
                    var exception = Assert.Throws<InvalidOperationException>(() =>
                        AgentInstallTarget.Resolve(
                            explicitTargetPath: null,
                            agent: AgentPlatform.Auto,
                            scope: InstallScope.Global,
                            projectDirectory: tempHome.Path));

                    Assert.Equal("No native agent platform detected for global scope. Create a native agent directory first or specify --agent/--target.", exception.Message);
                    return;
                }

                var layout = AgentInstallTarget.Resolve(
                    explicitTargetPath: null,
                    agent: AgentPlatform.Auto,
                    scope: InstallScope.Global,
                    projectDirectory: tempHome.Path);

                Assert.Equal(expected[0].Platform, layout.Agent);
                Assert.Equal(expected[0].Path, layout.PrimaryRoot.FullName);
                Assert.Equal(expected[0].Mode, layout.Mode);
            }
            finally
            {
                SetEnvironment("HOME", previousHome);
                SetEnvironment("USERPROFILE", previousUserProfile);
                SetEnvironment("CODEX_HOME", previousCodexHome);
            }
        }
    }

    [Fact]
    public void ResolveAutoGlobal_UsesCodexHomeEnvironmentWhenSet()
    {
        using var tempHome = new TemporaryDirectory();
        using var codexHome = new TemporaryDirectory();

        lock (TestEnvironmentLocks.UserProfile)
        {
            var previousHome = SetEnvironment("HOME", tempHome.Path);
            var previousUserProfile = SetEnvironment("USERPROFILE", tempHome.Path);
            var previousCodexHome = SetEnvironment("CODEX_HOME", codexHome.Path);

            try
            {
                Directory.CreateDirectory(codexHome.Path);

                var layout = AgentInstallTarget.Resolve(
                    explicitTargetPath: null,
                    agent: AgentPlatform.Auto,
                    scope: InstallScope.Global,
                    projectDirectory: tempHome.Path);

                Assert.Equal(AgentPlatform.Codex, layout.Agent);
                Assert.Equal(Path.Combine(codexHome.Path, "agents"), layout.PrimaryRoot.FullName);
                Assert.Equal(AgentInstallMode.CodexRoleFiles, layout.Mode);
            }
            finally
            {
                SetEnvironment("HOME", previousHome);
                SetEnvironment("USERPROFILE", previousUserProfile);
                SetEnvironment("CODEX_HOME", previousCodexHome);
            }
        }
    }

    [Theory]
    [MemberData(nameof(ExplicitTargetCases))]
    public void Resolve_WithExplicitTarget_UsesProvidedPathAndPlatformMode(object agent, object scope, object expectedMode)
    {
        using var tempDirectory = new TemporaryDirectory();
        var explicitPath = Path.Combine(tempDirectory.Path, "explicit-agents-target");

        var resolvedAgent = (AgentPlatform)agent;
        var resolvedScope = (InstallScope)scope;
        var resolvedMode = (AgentInstallMode)expectedMode;

        var layout = AgentInstallTarget.Resolve(
            explicitTargetPath: explicitPath,
            agent: resolvedAgent,
            scope: resolvedScope,
            projectDirectory: tempDirectory.Path);

        Assert.Equal(resolvedAgent, layout.Agent);
        Assert.Equal(resolvedScope, layout.Scope);
        Assert.Equal(resolvedMode, layout.Mode);
        Assert.True(layout.IsExplicitTarget);
        Assert.Equal(Path.GetFullPath(explicitPath), layout.PrimaryRoot.FullName);
    }

    [Fact]
    public void Resolve_WithExplicitTargetAndAutoAgent_Throws()
    {
        using var tempDirectory = new TemporaryDirectory();

        var exception = Assert.Throws<InvalidOperationException>(() =>
            AgentInstallTarget.Resolve(
                explicitTargetPath: Path.Combine(tempDirectory.Path, "explicit-agents-target"),
                agent: AgentPlatform.Auto,
                scope: InstallScope.Project,
                projectDirectory: tempDirectory.Path));

        Assert.Equal("Explicit agent targets require --agent because the installed file format depends on the target platform.", exception.Message);
    }

    public static IEnumerable<object[]> ProjectCases()
    {
        foreach (var hasCodex in new[] { false, true })
        foreach (var hasClaude in new[] { false, true })
        foreach (var hasCopilot in new[] { false, true })
        foreach (var hasGemini in new[] { false, true })
        foreach (var hasJunie in new[] { false, true })
        foreach (var hasSharedFallback in new[] { false, true })
        {
            yield return [hasCodex, hasClaude, hasCopilot, hasGemini, hasJunie, hasSharedFallback];
        }
    }

    public static IEnumerable<object[]> GlobalCases()
    {
        foreach (var hasCodex in new[] { false, true })
        foreach (var hasClaude in new[] { false, true })
        foreach (var hasCopilot in new[] { false, true })
        foreach (var hasGemini in new[] { false, true })
        foreach (var hasJunie in new[] { false, true })
        foreach (var hasSharedFallback in new[] { false, true })
        {
            yield return [hasCodex, hasClaude, hasCopilot, hasGemini, hasJunie, hasSharedFallback];
        }
    }

    public static IEnumerable<object[]> ExplicitTargetCases()
    {
        yield return [AgentPlatform.Codex, InstallScope.Project, AgentInstallMode.CodexRoleFiles];
        yield return [AgentPlatform.Codex, InstallScope.Global, AgentInstallMode.CodexRoleFiles];
        yield return [AgentPlatform.Claude, InstallScope.Project, AgentInstallMode.MarkdownAgentFiles];
        yield return [AgentPlatform.Claude, InstallScope.Global, AgentInstallMode.MarkdownAgentFiles];
        yield return [AgentPlatform.Copilot, InstallScope.Project, AgentInstallMode.CopilotAgentFiles];
        yield return [AgentPlatform.Copilot, InstallScope.Global, AgentInstallMode.CopilotAgentFiles];
        yield return [AgentPlatform.Gemini, InstallScope.Project, AgentInstallMode.MarkdownAgentFiles];
        yield return [AgentPlatform.Gemini, InstallScope.Global, AgentInstallMode.MarkdownAgentFiles];
        yield return [AgentPlatform.Junie, InstallScope.Project, AgentInstallMode.MarkdownAgentFiles];
        yield return [AgentPlatform.Junie, InstallScope.Global, AgentInstallMode.MarkdownAgentFiles];
    }

    private static IReadOnlyList<ResolvedLayout> BuildExpectedProjectLayouts(
        string rootPath,
        bool hasCodex,
        bool hasClaude,
        bool hasCopilot,
        bool hasGemini,
        bool hasJunie)
    {
        var layouts = new List<ResolvedLayout>();

        if (hasCodex)
        {
            layouts.Add(new ResolvedLayout(AgentPlatform.Codex, Path.Combine(rootPath, ".codex", "agents"), AgentInstallMode.CodexRoleFiles));
        }

        if (hasClaude)
        {
            layouts.Add(new ResolvedLayout(AgentPlatform.Claude, Path.Combine(rootPath, ".claude", "agents"), AgentInstallMode.MarkdownAgentFiles));
        }

        if (hasCopilot)
        {
            layouts.Add(new ResolvedLayout(AgentPlatform.Copilot, Path.Combine(rootPath, ".github", "agents"), AgentInstallMode.CopilotAgentFiles));
        }

        if (hasGemini)
        {
            layouts.Add(new ResolvedLayout(AgentPlatform.Gemini, Path.Combine(rootPath, ".gemini", "agents"), AgentInstallMode.MarkdownAgentFiles));
        }

        if (hasJunie)
        {
            layouts.Add(new ResolvedLayout(AgentPlatform.Junie, Path.Combine(rootPath, ".junie", "agents"), AgentInstallMode.MarkdownAgentFiles));
        }

        return layouts;
    }

    private static IReadOnlyList<ResolvedLayout> BuildExpectedGlobalLayouts(
        string homePath,
        bool hasCodex,
        bool hasClaude,
        bool hasCopilot,
        bool hasGemini,
        bool hasJunie)
    {
        var layouts = new List<ResolvedLayout>();

        if (hasCodex)
        {
            layouts.Add(new ResolvedLayout(AgentPlatform.Codex, Path.Combine(homePath, ".codex", "agents"), AgentInstallMode.CodexRoleFiles));
        }

        if (hasClaude)
        {
            layouts.Add(new ResolvedLayout(AgentPlatform.Claude, Path.Combine(homePath, ".claude", "agents"), AgentInstallMode.MarkdownAgentFiles));
        }

        if (hasCopilot)
        {
            layouts.Add(new ResolvedLayout(AgentPlatform.Copilot, Path.Combine(homePath, ".copilot", "agents"), AgentInstallMode.CopilotAgentFiles));
        }

        if (hasGemini)
        {
            layouts.Add(new ResolvedLayout(AgentPlatform.Gemini, Path.Combine(homePath, ".gemini", "agents"), AgentInstallMode.MarkdownAgentFiles));
        }

        if (hasJunie)
        {
            layouts.Add(new ResolvedLayout(AgentPlatform.Junie, Path.Combine(homePath, ".junie", "agents"), AgentInstallMode.MarkdownAgentFiles));
        }

        return layouts;
    }

    private static void CreatePlatformDirectories(
        string rootDirectory,
        bool hasCodex,
        bool hasClaude,
        bool hasCopilot,
        bool hasGemini,
        bool hasJunie,
        bool hasSharedFallback)
    {
        if (hasCodex)
        {
            Directory.CreateDirectory(Path.Combine(rootDirectory, ".codex"));
        }

        if (hasClaude)
        {
            Directory.CreateDirectory(Path.Combine(rootDirectory, ".claude"));
        }

        if (hasCopilot)
        {
            Directory.CreateDirectory(Path.Combine(rootDirectory, ".copilot"));
            Directory.CreateDirectory(Path.Combine(rootDirectory, ".github"));
        }

        if (hasGemini)
        {
            Directory.CreateDirectory(Path.Combine(rootDirectory, ".gemini"));
        }

        if (hasJunie)
        {
            Directory.CreateDirectory(Path.Combine(rootDirectory, ".junie"));
        }

        if (hasSharedFallback)
        {
            Directory.CreateDirectory(Path.Combine(rootDirectory, ".agents"));
        }
    }

    private static string? SetEnvironment(string variable, string? value)
    {
        var previous = Environment.GetEnvironmentVariable(variable);
        Environment.SetEnvironmentVariable(variable, value);
        return previous;
    }

    private sealed record ResolvedLayout(AgentPlatform Platform, string Path, AgentInstallMode Mode);
}

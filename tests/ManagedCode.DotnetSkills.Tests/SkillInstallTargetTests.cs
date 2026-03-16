using ManagedCode.DotnetSkills.Runtime;

namespace ManagedCode.DotnetSkills.Tests;

public sealed class SkillInstallTargetTests
{
    [Fact]
    public void ResolveAutoProject_PrefersCodexRootBeforeOtherAgentFolders()
    {
        using var tempDirectory = new TemporaryDirectory();
        Directory.CreateDirectory(System.IO.Path.Combine(tempDirectory.Path, ".codex"));
        Directory.CreateDirectory(System.IO.Path.Combine(tempDirectory.Path, ".claude"));
        Directory.CreateDirectory(System.IO.Path.Combine(tempDirectory.Path, ".github"));

        var layout = SkillInstallTarget.Resolve(
            explicitTargetPath: null,
            agent: AgentPlatform.Auto,
            scope: InstallScope.Project,
            projectDirectory: tempDirectory.Path);

        Assert.Equal(AgentPlatform.Codex, layout.Agent);
        Assert.Equal(SkillInstallMode.RawSkillPayloads, layout.Mode);
        Assert.Equal(System.IO.Path.Combine(tempDirectory.Path, ".codex", "skills"), layout.PrimaryRoot.FullName);
    }
}

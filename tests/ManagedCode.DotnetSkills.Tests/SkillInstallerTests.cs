using ManagedCode.DotnetSkills.Runtime;

namespace ManagedCode.DotnetSkills.Tests;

public sealed class SkillInstallerTests
{
    [Fact]
    public void SelectSkills_ResolvesShortAliases()
    {
        var catalog = TestCatalog.Load();
        var installer = new SkillInstaller(catalog);

        var selected = installer.SelectSkills(["aspire", "dotnet-orleans"], installAll: false);

        Assert.Equal(["dotnet-aspire", "dotnet-orleans"], selected.Select(skill => skill.Name).ToArray());
    }

    [Fact]
    public void InstallAndRemove_RawSkillPayloads_TracksInstalledVersions()
    {
        var catalog = TestCatalog.Load();
        var installer = new SkillInstaller(catalog);
        using var tempDirectory = new TemporaryDirectory();
        var layout = SkillInstallTarget.Resolve(tempDirectory.Path, AgentPlatform.Codex, InstallScope.Project, projectDirectory: null);
        var selected = installer.SelectSkills(["aspire", "orleans"], installAll: false);

        var installSummary = installer.Install(selected, layout, force: false);
        var installed = installer.GetInstalledSkills(layout);

        Assert.Equal(2, installSummary.InstalledCount);
        Assert.Equal(2, installed.Count);
        Assert.All(installed, record => Assert.True(record.IsCurrent));
        Assert.Contains(installed, record => record.Skill.Name == "dotnet-aspire");
        Assert.True(File.Exists(System.IO.Path.Combine(tempDirectory.Path, "dotnet-aspire", "SKILL.md")));

        var removeSummary = installer.Remove([selected[0]], layout);
        var remaining = installer.GetInstalledSkills(layout);

        Assert.Equal(1, removeSummary.RemovedCount);
        Assert.Empty(removeSummary.MissingSkills);
        Assert.DoesNotContain(remaining, record => record.Skill.Name == "dotnet-aspire");
        Assert.True(File.Exists(System.IO.Path.Combine(tempDirectory.Path, "dotnet-orleans", "SKILL.md")));
    }

    [Fact]
    public void InstallAndRemove_ClaudeSubagents_UsesGeneratedAdapterVersion()
    {
        var catalog = TestCatalog.Load();
        var installer = new SkillInstaller(catalog);
        using var tempDirectory = new TemporaryDirectory();
        var layout = SkillInstallTarget.Resolve(tempDirectory.Path, AgentPlatform.Claude, InstallScope.Project, projectDirectory: null);
        var selected = installer.SelectSkills(["aspire"], installAll: false);

        installer.Install(selected, layout, force: false);
        var installed = installer.GetInstalledSkills(layout);

        var record = Assert.Single(installed);
        Assert.Equal("dotnet-aspire", record.Skill.Name);
        Assert.Equal(record.Skill.Version, record.InstalledVersion);
        Assert.True(File.Exists(System.IO.Path.Combine(tempDirectory.Path, "dotnet-aspire.md")));

        var removeSummary = installer.Remove(selected, layout);

        Assert.Equal(1, removeSummary.RemovedCount);
        Assert.False(File.Exists(System.IO.Path.Combine(tempDirectory.Path, "dotnet-aspire.md")));
    }
}

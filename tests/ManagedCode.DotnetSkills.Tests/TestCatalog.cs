using ManagedCode.DotnetSkills.Runtime;

namespace ManagedCode.DotnetSkills.Tests;

internal static class TestCatalog
{
    public static SkillCatalogPackage Load()
    {
        var repositoryRoot = ResolveRepositoryRoot();
        return SkillCatalogPackage.LoadFromDirectory(repositoryRoot, "repository source", "test");
    }

    private static DirectoryInfo ResolveRepositoryRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);

        while (directory is not null)
        {
            if (File.Exists(Path.Combine(directory.FullName, "dotnet-skills.slnx")))
            {
                return directory;
            }

            directory = directory.Parent;
        }

        throw new InvalidOperationException("Could not locate the repository root from the test output directory.");
    }
}

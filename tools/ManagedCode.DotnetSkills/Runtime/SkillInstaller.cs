using System.Text.RegularExpressions;

namespace ManagedCode.DotnetSkills.Runtime;

internal sealed class SkillInstaller(SkillCatalogPackage catalog)
{
    public IReadOnlyList<SkillEntry> SelectSkills(IReadOnlyList<string> requestedSkills, bool installAll)
    {
        if (installAll || requestedSkills.Count == 0)
        {
            return catalog.Skills.OrderBy(skill => skill.Name, StringComparer.Ordinal).ToArray();
        }

        var available = catalog.Skills.ToDictionary(skill => skill.Name, StringComparer.OrdinalIgnoreCase);
        var selected = new List<SkillEntry>();

        foreach (var skillName in requestedSkills)
        {
            if (!TryResolveSkill(available, skillName, out var skill))
            {
                throw new InvalidOperationException($"Unknown skill: {skillName}");
            }

            selected.Add(skill);
        }

        return selected;
    }

    public SkillInstallSummary Install(IReadOnlyList<SkillEntry> skills, SkillInstallLayout layout, bool force)
    {
        layout.PrimaryRoot.Create();

        var installedCount = 0;
        var generatedAdapters = 0;
        var skippedExisting = new List<string>();

        foreach (var skill in skills)
        {
            var sourceDirectory = catalog.ResolveSkillSource(skill.Name);
            switch (layout.Mode)
            {
                case SkillInstallMode.RawSkillPayloads:
                    {
                        var destinationDirectory = new DirectoryInfo(Path.Combine(layout.PrimaryRoot.FullName, skill.Name));

                        if (destinationDirectory.Exists)
                        {
                            if (!force)
                            {
                                skippedExisting.Add(skill.Name);
                                continue;
                            }

                            destinationDirectory.Delete(recursive: true);
                        }

                        CopyDirectory(sourceDirectory, destinationDirectory);
                        installedCount++;
                        break;
                    }
                case SkillInstallMode.ClaudeSubagents:
                    {
                        var destinationFile = new FileInfo(Path.Combine(layout.PrimaryRoot.FullName, $"{skill.Name}.md"));
                        if (destinationFile.Exists && !force)
                        {
                            skippedExisting.Add(skill.Name);
                            continue;
                        }

                        WriteClaudeAdapter(layout.PrimaryRoot, sourceDirectory, skill);
                        installedCount++;
                        generatedAdapters++;
                        break;
                    }
                default:
                    throw new InvalidOperationException($"Unsupported install mode: {layout.Mode}");
            }
        }

        return new SkillInstallSummary(installedCount, generatedAdapters, skippedExisting);
    }

    public SkillRemoveSummary Remove(IReadOnlyList<SkillEntry> skills, SkillInstallLayout layout)
    {
        var removedCount = 0;
        var missingSkills = new List<string>();

        foreach (var skill in skills)
        {
            switch (layout.Mode)
            {
                case SkillInstallMode.RawSkillPayloads:
                    {
                        var destinationDirectory = new DirectoryInfo(Path.Combine(layout.PrimaryRoot.FullName, skill.Name));
                        if (!destinationDirectory.Exists)
                        {
                            missingSkills.Add(skill.Name);
                            continue;
                        }

                        destinationDirectory.Delete(recursive: true);
                        removedCount++;
                        break;
                    }
                case SkillInstallMode.ClaudeSubagents:
                    {
                        var destinationFile = new FileInfo(Path.Combine(layout.PrimaryRoot.FullName, $"{skill.Name}.md"));
                        if (!destinationFile.Exists)
                        {
                            missingSkills.Add(skill.Name);
                            continue;
                        }

                        destinationFile.Delete();
                        removedCount++;
                        break;
                    }
                default:
                    throw new InvalidOperationException($"Unsupported install mode: {layout.Mode}");
            }
        }

        return new SkillRemoveSummary(removedCount, missingSkills);
    }

    public bool IsInstalled(SkillEntry skill, SkillInstallLayout layout)
    {
        return layout.Mode switch
        {
            SkillInstallMode.RawSkillPayloads => Directory.Exists(Path.Combine(layout.PrimaryRoot.FullName, skill.Name)),
            SkillInstallMode.ClaudeSubagents => File.Exists(Path.Combine(layout.PrimaryRoot.FullName, $"{skill.Name}.md")),
            _ => false,
        };
    }

    public IReadOnlyList<InstalledSkillRecord> GetInstalledSkills(SkillInstallLayout layout)
    {
        return catalog.Skills
            .Where(skill => IsInstalled(skill, layout))
            .Select(skill => new InstalledSkillRecord(skill, ReadInstalledVersion(skill, layout)))
            .OrderBy(record => record.Skill.Name, StringComparer.Ordinal)
            .ToArray();
    }

    public static void CopyDirectory(DirectoryInfo source, DirectoryInfo destination)
    {
        destination.Create();

        foreach (var file in source.GetFiles())
        {
            var targetPath = Path.Combine(destination.FullName, file.Name);
            file.CopyTo(targetPath, overwrite: true);
        }

        foreach (var childDirectory in source.GetDirectories())
        {
            var childDestination = new DirectoryInfo(Path.Combine(destination.FullName, childDirectory.Name));
            CopyDirectory(childDirectory, childDestination);
        }
    }

    private static bool TryResolveSkill(
        IReadOnlyDictionary<string, SkillEntry> available,
        string requestedSkill,
        out SkillEntry skill)
    {
        if (available.TryGetValue(requestedSkill, out skill!))
        {
            return true;
        }

        if (!requestedSkill.StartsWith("dotnet-", StringComparison.OrdinalIgnoreCase))
        {
            return available.TryGetValue($"dotnet-{requestedSkill}", out skill!);
        }

        return false;
    }

    private static void WriteClaudeAdapter(DirectoryInfo adapterRoot, DirectoryInfo sourceDirectory, SkillEntry skill)
    {
        adapterRoot.Create();

        var adapterPath = Path.Combine(adapterRoot.FullName, $"{skill.Name}.md");
        var skillMarkdown = ExtractSkillMarkdown(sourceDirectory);

        var contents =
            $"""
            ---
            name: {skill.Name}
            version: {skill.Version}
            description: "{EscapeYaml(skill.Description)}"
            ---

            Generated from the `dotnet-skills` catalog.
            Source skill: `{skill.Name}` version `{skill.Version}`.

            {skillMarkdown}
            """;

        File.WriteAllText(adapterPath, contents);
    }

    private static string ExtractSkillMarkdown(DirectoryInfo sourceDirectory)
    {
        var skillFile = new FileInfo(Path.Combine(sourceDirectory.FullName, "SKILL.md"));
        if (!skillFile.Exists)
        {
            throw new InvalidOperationException($"Claude adapter generation requires {skillFile.FullName}");
        }

        var text = File.ReadAllText(skillFile.FullName);
        if (!text.StartsWith("---\n", StringComparison.Ordinal))
        {
            return text.Trim();
        }

        var marker = "\n---\n";
        var markerIndex = text.IndexOf(marker, startIndex: 4, StringComparison.Ordinal);
        if (markerIndex < 0)
        {
            return text.Trim();
        }

        return text[(markerIndex + marker.Length)..].Trim();
    }

    private static string EscapeYaml(string value) => value.Replace("\\", "\\\\").Replace("\"", "\\\"");

    private static string ReadInstalledVersion(SkillEntry skill, SkillInstallLayout layout)
    {
        return layout.Mode switch
        {
            SkillInstallMode.RawSkillPayloads => ReadFrontMatterValue(Path.Combine(layout.PrimaryRoot.FullName, skill.Name, "SKILL.md"), "version") ?? "unknown",
            SkillInstallMode.ClaudeSubagents => ReadFrontMatterValue(Path.Combine(layout.PrimaryRoot.FullName, $"{skill.Name}.md"), "version")
                ?? ReadClaudeAdapterVersion(Path.Combine(layout.PrimaryRoot.FullName, $"{skill.Name}.md"))
                ?? "unknown",
            _ => "unknown",
        };
    }

    private static string? ReadFrontMatterValue(string filePath, string key)
    {
        if (!File.Exists(filePath))
        {
            return null;
        }

        var lines = File.ReadLines(filePath).ToArray();
        if (lines.Length == 0 || lines[0] != "---")
        {
            return null;
        }

        for (var index = 1; index < lines.Length; index++)
        {
            var line = lines[index];
            if (line == "---")
            {
                break;
            }

            if (!line.StartsWith($"{key}:", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            return line[(line.IndexOf(':', StringComparison.Ordinal) + 1)..].Trim().Trim('"');
        }

        return null;
    }

    private static string? ReadClaudeAdapterVersion(string filePath)
    {
        if (!File.Exists(filePath))
        {
            return null;
        }

        var text = File.ReadAllText(filePath);
        var match = Regex.Match(text, @"Source skill: `[^`]+` version `([^`]+)`\.");
        return match.Success ? match.Groups[1].Value : null;
    }
}

internal sealed record SkillInstallSummary(int InstalledCount, int GeneratedAdapters, IReadOnlyList<string> SkippedExisting);
internal sealed record SkillRemoveSummary(int RemovedCount, IReadOnlyList<string> MissingSkills);
internal sealed record InstalledSkillRecord(SkillEntry Skill, string InstalledVersion)
{
    public bool IsCurrent => string.Equals(InstalledVersion, Skill.Version, StringComparison.OrdinalIgnoreCase);
}

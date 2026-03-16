# AnalysisLevel and .editorconfig Configuration

This reference covers MSBuild properties for SDK analyzers and .editorconfig settings for rule configuration.

## MSBuild Properties

Configure these in `Directory.Build.props` or individual project files.

### EnableNETAnalyzers

```xml
<PropertyGroup>
  <EnableNETAnalyzers>true</EnableNETAnalyzers>
</PropertyGroup>
```

- Enabled by default in .NET 5+.
- Set explicitly for clarity and to prevent accidental disabling.

### AnalysisLevel

Controls which rules are enabled based on .NET version and analysis mode.

```xml
<PropertyGroup>
  <AnalysisLevel>latest</AnalysisLevel>
</PropertyGroup>
```

| Value | Meaning |
|-------|---------|
| `5.0`, `6.0`, `7.0`, `8.0`, `9.0`, `10.0` | Rules available in that SDK version |
| `latest` | Rules from the installed SDK version |
| `latest-recommended` | Latest SDK with Recommended mode |
| `latest-minimum` | Latest SDK with Minimum mode |
| `latest-all` | Latest SDK with All mode |
| `preview` | Experimental rules from preview SDK |

### AnalysisMode

Controls which subset of rules are enabled.

```xml
<PropertyGroup>
  <AnalysisMode>Recommended</AnalysisMode>
</PropertyGroup>
```

| Mode | Description |
|------|-------------|
| `None` | All rules disabled except explicitly enabled |
| `Default` | Default severity for all rules (same as not setting) |
| `Minimum` | Small set of critical rules |
| `Recommended` | Common high-value rules (start here) |
| `All` | Every available rule |

### Combined Syntax

AnalysisLevel can include the mode:

```xml
<PropertyGroup>
  <AnalysisLevel>latest-recommended</AnalysisLevel>
</PropertyGroup>
```

This is equivalent to:

```xml
<PropertyGroup>
  <AnalysisLevel>latest</AnalysisLevel>
  <AnalysisMode>Recommended</AnalysisMode>
</PropertyGroup>
```

### Category-Specific AnalysisMode

Override mode for specific categories:

```xml
<PropertyGroup>
  <AnalysisLevel>latest-recommended</AnalysisLevel>
  <AnalysisModeSecurity>All</AnalysisModeSecurity>
  <AnalysisModeReliability>All</AnalysisModeReliability>
</PropertyGroup>
```

Available categories: `Design`, `Documentation`, `Globalization`, `Interoperability`, `Maintainability`, `Naming`, `Performance`, `Reliability`, `Security`, `Usage`.

### TreatWarningsAsErrors

```xml
<PropertyGroup>
  <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
</PropertyGroup>
```

Makes all warnings fail the build. Best for new projects or mature codebases that have already cleared their warning backlog. Combine with `WarningsNotAsErrors` for explicit exceptions.

**Agent rule**: never disable, remove, or comment out this property to make a build pass. Fix the code instead or ask the user.

### WarningsAsErrors (Selective — Preferred for Legacy Codebases)

```xml
<PropertyGroup>
  <WarningsAsErrors>CS8019;CS0219;CS0168;CA2000;CA3001</WarningsAsErrors>
</PropertyGroup>
```

Promote specific warnings to errors without affecting others. This is the recommended approach for gradual adoption in legacy projects:

1. Start with trivial hygiene warnings (CS8019 unused usings, CS0219/CS0168 unused variables).
2. Fix all occurrences in the codebase.
3. Add the IDs to `WarningsAsErrors` so they stay enforced.
4. Ask the user which category to promote next.
5. Repeat until the codebase is clean enough to switch to `TreatWarningsAsErrors`.

**Agent rule**: never remove IDs from this list to make a build pass. The user chose these IDs deliberately.

### WarningsNotAsErrors

```xml
<PropertyGroup>
  <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
  <WarningsNotAsErrors>CA1707</WarningsNotAsErrors>
</PropertyGroup>
```

Keep specific warnings as warnings when using `TreatWarningsAsErrors`. Use this for rules the team has explicitly decided to defer.

### NoWarn

```xml
<PropertyGroup>
  <NoWarn>$(NoWarn);CA1062</NoWarn>
</PropertyGroup>
```

Disable specific warnings entirely. Use sparingly; prefer .editorconfig for visibility.

### EnforceCodeStyleInBuild

```xml
<PropertyGroup>
  <EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>
</PropertyGroup>
```

Enable IDE code style rules during build (disabled by default for performance).

## .editorconfig Configuration

Place at repository root. Rules cascade to subdirectories.

### Basic Structure

```editorconfig
# Top-level settings
root = true

[*.cs]
# All C# files

[*.{cs,vb}]
# All .NET code files

[**/Tests/**/*.cs]
# Test files only
```

### Analyzer Severity Configuration

```editorconfig
[*.cs]
# Set specific rule severity
dotnet_diagnostic.CA1000.severity = warning
dotnet_diagnostic.CA2000.severity = error
dotnet_diagnostic.CA1707.severity = none

# Bulk category severity (requires .NET 6+)
dotnet_analyzer_diagnostic.category-Security.severity = error
dotnet_analyzer_diagnostic.category-Performance.severity = warning
```

### Common Patterns

#### Production Code Hardened

```editorconfig
[*.cs]
# Security rules as errors
dotnet_analyzer_diagnostic.category-Security.severity = error

# Reliability rules as warnings
dotnet_analyzer_diagnostic.category-Reliability.severity = warning

# Performance rules as warnings
dotnet_analyzer_diagnostic.category-Performance.severity = warning
```

#### Test Code Relaxed

```editorconfig
[**/Tests/**/*.cs]
[**/Test/**/*.cs]
[**/*.Tests/**/*.cs]
# Relax naming rules for test methods
dotnet_diagnostic.CA1707.severity = none

# Relax null checks for test assertions
dotnet_diagnostic.CA1062.severity = none

# Allow test-specific patterns
dotnet_diagnostic.CA2007.severity = none
```

#### Generated Code Excluded

```editorconfig
[*.generated.cs]
[*.designer.cs]
generated_code = true
```

### Code Style Settings

```editorconfig
[*.cs]
# Namespace preferences
csharp_style_namespace_declarations = file_scoped:suggestion

# Expression-bodied members
csharp_style_expression_bodied_methods = when_on_single_line:suggestion
csharp_style_expression_bodied_properties = true:suggestion

# Pattern matching
csharp_style_pattern_matching_over_as_with_null_check = true:warning
csharp_style_pattern_matching_over_is_with_cast_check = true:warning

# Null checking
csharp_style_prefer_null_check_over_type_check = true:suggestion

# var preferences
csharp_style_var_for_built_in_types = true:suggestion
csharp_style_var_when_type_is_apparent = true:suggestion
csharp_style_var_elsewhere = true:suggestion
```

### Formatting Settings

```editorconfig
[*.cs]
# Indentation
indent_style = space
indent_size = 4
tab_width = 4

# New lines
csharp_new_line_before_open_brace = all
csharp_new_line_before_else = true
csharp_new_line_before_catch = true
csharp_new_line_before_finally = true
```

## Recommended Starting Configuration

### Directory.Build.props

```xml
<Project>
  <PropertyGroup>
    <EnableNETAnalyzers>true</EnableNETAnalyzers>
    <AnalysisLevel>latest-recommended</AnalysisLevel>
    <EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>
  </PropertyGroup>

  <PropertyGroup Condition="'$(Configuration)' == 'Release'">
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
  </PropertyGroup>
</Project>
```

### .editorconfig (Root)

```editorconfig
root = true

[*]
indent_style = space
indent_size = 4
end_of_line = lf
charset = utf-8
trim_trailing_whitespace = true
insert_final_newline = true

[*.cs]
# Security rules as errors
dotnet_analyzer_diagnostic.category-Security.severity = error

# Reliability rules as warnings, promote over time
dotnet_analyzer_diagnostic.category-Reliability.severity = warning

# Relax test files
[**/Tests/**/*.cs]
dotnet_diagnostic.CA1707.severity = none
dotnet_diagnostic.CA1062.severity = none
```

## Verification Commands

```bash
# Build with analyzer output
dotnet build

# Build with detailed analyzer timing
dotnet build /p:ReportAnalyzer=true

# Check effective analyzer configuration
dotnet build /v:d | grep -i "analyzer"
```

## References

- [AnalysisLevel documentation](https://learn.microsoft.com/en-us/dotnet/core/project-sdk/msbuild-props#analysislevel)
- [Code analysis configuration](https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/configuration-options)
- [EditorConfig settings](https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/configuration-files)
- [Suppress warnings](https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/suppress-warnings)

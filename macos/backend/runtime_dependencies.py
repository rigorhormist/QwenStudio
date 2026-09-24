"""Validate only Qwen Studio's dependency graph, not other applications in Python."""
from importlib import metadata

ROOT_REQUIREMENTS = (
    'torch>=2.9.0', 'torchvision>=0.24.0', 'transformers>=5.17.0',
    'diffusers', 'accelerate>=1.12.0', 'Pillow>=12.0.0',
    'psutil>=7.1.3', 'filelock>=3.20.0', 'safetensors',
    'huggingface_hub', 'numpy', 'tokenizers', 'packaging',
)


def check_dependencies(lookup=metadata.distribution, roots=ROOT_REQUIREMENTS):
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    pending = [(Requirement(value), 'Qwen Studio') for value in roots]
    visited, problems = set(), []
    while pending:
        requirement, parent = pending.pop()
        name = canonicalize_name(requirement.name)
        try:
            distribution = lookup(requirement.name)
        except metadata.PackageNotFoundError:
            problems.append(f'{parent} requires {requirement}; it is not installed.')
            continue
        if requirement.specifier and not requirement.specifier.contains(distribution.version, prereleases=True):
            problems.append(f'{parent} requires {requirement}; installed {distribution.version}.')
        key = (name, tuple(sorted(requirement.extras)))
        if key in visited:
            continue
        visited.add(key)
        for value in distribution.requires or ():
            child = Requirement(value)
            extras = {'', *requirement.extras}
            if child.marker is None or any(child.marker.evaluate({'extra': extra}) for extra in extras):
                pending.append((child, requirement.name))
    if problems:
        raise RuntimeError('\n'.join(sorted(set(problems))))
    return '依赖版本兼容'

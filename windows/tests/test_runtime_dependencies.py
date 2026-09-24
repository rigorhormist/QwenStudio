import sys
import unittest
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from runtime_dependencies import check_dependencies


class DependencyScopeTests(unittest.TestCase):
    def lookup(self, packages):
        def get(name):
            if name not in packages:raise metadata.PackageNotFoundError(name)
            version,requires=packages[name]
            return SimpleNamespace(version=version,requires=requires)
        return get

    def test_unrelated_application_cannot_block_studio(self):
        packages={'transformers':('5.17.0',['tokenizers>=0.23']),
                  'tokenizers':('0.23.2',[]),
                  'zhpr':('0.1.3',['transformers<5','pandas<2'])}
        self.assertEqual(check_dependencies(self.lookup(packages),['transformers==5.17.0']),'依赖版本兼容')

    def test_real_transitive_conflict_and_missing_package_are_blocked(self):
        for dependencies in ({'tokenizers':('0.20',[])},{}):
            packages={'transformers':('5.17.0',['tokenizers>=0.23']),**dependencies}
            with self.assertRaisesRegex(RuntimeError,'tokenizers'):
                check_dependencies(self.lookup(packages),['transformers'])

    def test_extras_markers_and_cycles(self):
        packages={'app':('1',['base>=1','feature; extra == "gpu"','missing; python_version < "3"']),
                  'base':('1',['app']), 'feature':('1',[])}
        self.assertEqual(check_dependencies(self.lookup(packages),['app[gpu]']),'依赖版本兼容')
        del packages['feature']
        self.assertEqual(check_dependencies(self.lookup(packages),['app']),'依赖版本兼容')
        with self.assertRaisesRegex(RuntimeError,'feature'):
            check_dependencies(self.lookup(packages),['app[gpu]'])


if __name__=='__main__':unittest.main()

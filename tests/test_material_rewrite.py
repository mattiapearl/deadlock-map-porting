import tempfile
import unittest
from pathlib import Path

from tools.full_recompile_workshop_map import rewrite_vmat


class MaterialRewriteTests(unittest.TestCase):
    def rewrite(self, text: str, name: str = "test.vmat"):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / name
            p.write_text(text, encoding="utf-8")
            kind = rewrite_vmat(p)
            return kind, p.read_text(encoding="utf-8")

    def test_emissive_csgo_complex_preserves_self_illum(self):
        kind, out = self.rewrite('''"Layer0"\n{\n "shader" "csgo_complex.vfx"\n "F_SELF_ILLUM" "1"\n "TextureColor" "materials/rbx/glowingblue.png"\n "TextureSelfIllumMask" "materials/rbx/glowingblue.png"\n "g_flSelfIllumScale" "1"\n}\n''')
        self.assertEqual(kind, "emissive_pbr")
        self.assertIn('"shader"\t"pbr.vfx"', out)
        self.assertIn('"F_UNLIT"\t"1"', out)
        self.assertIn('"F_SELF_ILLUM"\t"1"', out)
        self.assertIn('"TextureSelfIllumMask1"\t"materials/rbx/glowingblue.png"', out)
        self.assertIn('"g_flSelfIllumScale1"\t"2.500000"', out)

    def test_lightmappedgeneric_becomes_enriched_or_plain_pbr(self):
        kind, out = self.rewrite('''"Layer0"\n{\n "shader" "csgo_lightmappedgeneric.vfx"\n "TextureColor" "materials/dev/dev.png"\n "TextureLayer1NormalRoughness" "materials/dev/nr.png"\n}\n''')
        self.assertEqual(kind, "enriched_pbr")
        self.assertIn('"TextureColor1"\t"materials/dev/dev.png"', out)
        self.assertIn('"TextureNormal1"\t"materials/dev/nr.png"', out)

    def test_translucent_material_classified(self):
        kind, out = self.rewrite('''"Layer0"\n{\n "shader" "csgo_lightmappedgeneric.vfx"\n "F_TRANSLUCENT" "1"\n "TextureColor" "materials/glass/a.png"\n}\n''')
        self.assertIn(kind, {"translucent_pbr", "glass_pbr"})
        self.assertIn("pbr.vfx", out)

    def test_moondome_becomes_sky_fallback(self):
        kind, out = self.rewrite('''"Layer0"\n{\n "shader" "csgo_moondome.vfx"\n "TextureColor" "materials/skybox/moon.png"\n}\n''', "moondome.vmat")
        self.assertEqual(kind, "sky")
        self.assertIn('"shader"\t"sky.vfx"', out)
        self.assertIn("sky_dl_dusk03", out)


if __name__ == "__main__":
    unittest.main()

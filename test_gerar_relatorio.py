import unittest
from datetime import datetime

import gerar_relatorio


class GerarRelatorioTests(unittest.TestCase):
    def test_gera_html_com_preco_pack(self):
        produtos = [
            {
                "site": "Sam's Club",
                "marca_buscada": "Heineken",
                "produto": "Cerveja Heineken Long Neck",
                "url": "https://example.com/produto/1",
                "preco_pack": "12,90",
            }
        ]

        html = gerar_relatorio.gerar_html(produtos, datetime(2026, 7, 6))

        self.assertIn("Cervejas", html)
        self.assertIn("R$ 12,90", html)


if __name__ == "__main__":
    unittest.main()

"""
Multi-Marketplace Feed Generator Service
Section 16 — Mode Lens Production Vocabulary & Taxonomy Registry v1.0
Generates compliant feeds for Shopify, Amazon, Zalando, ASOS, Farfetch.
"""
import csv
import json
import io
from datetime import datetime
from typing import List, Dict, Any, Optional


# ========================== Marketplace Configs =================

MARKETPLACE_CONFIGS = {
    "shopify": {
        "name": "Shopify",
        "format": "csv",
        "fields": [
            "Handle", "Title", "Body (HTML)", "Vendor", "Type", "Tags",
            "Published", "Option1 Name", "Option1 Value", "Option2 Name",
            "Option2 Value", "Variant SKU", "Variant Price", "Image Src",
            "Image Alt Text", "Status"
        ],
    },
    "amazon": {
        "name": "Amazon Standard Feed",
        "format": "csv",
        "fields": [
            "item_sku", "item_name", "external_product_id", "brand_name",
            "feed_product_type", "color_name", "size_name", "main_image_url",
            "other_image_url1", "other_image_url2", "list_price",
            "quantity", "condition_type", "description"
        ],
    },
    "zalando": {
        "name": "Zalando",
        "format": "json",
        "fields": [
            "ean", "name", "brand", "category", "color", "size",
            "price", "images", "description", "gender"
        ],
    },
    "asos": {
        "name": "ASOS",
        "format": "csv",
        "fields": [
            "ProductCode", "ProductName", "Brand", "Category", "Colour",
            "Size", "Price", "MainImageURL", "AltImageURL1", "AltImageURL2",
            "Description", "Gender"
        ],
    },
    "farfetch": {
        "name": "Farfetch",
        "format": "json",
        "fields": [
            "reference", "name", "designer", "category", "color",
            "sizes", "price", "currency", "images", "description"
        ],
    },
}

# Standard catalog angles
CATALOG_ANGLES = [
    {"code": "FRONT", "label": "Front View", "yaw": 0},
    {"code": "HERO_45", "label": "45° Hero", "yaw": 45},
    {"code": "SIDE", "label": "Side Profile", "yaw": 90},
    {"code": "BACK", "label": "Back View", "yaw": 180},
    {"code": "MACRO", "label": "Macro Detail", "yaw": 0},
]


class MarketplaceService:
    """Generates marketplace-compliant product feeds."""

    def generate_shopify_csv(self, skus: List[Dict]) -> str:
        """Generate Shopify CSV feed."""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=MARKETPLACE_CONFIGS["shopify"]["fields"])
        writer.writeheader()

        for sku in skus:
            images = sku.get("images", [])
            writer.writerow({
                "Handle": sku.get("sku_tag", "").lower().replace(" ", "-"),
                "Title": sku.get("product_name", ""),
                "Body (HTML)": f"<p>{sku.get('description', '')}</p>",
                "Vendor": sku.get("brand_name", ""),
                "Type": sku.get("category", ""),
                "Tags": ", ".join(sku.get("tags", [])),
                "Published": "TRUE",
                "Option1 Name": "Color",
                "Option1 Value": sku.get("color", ""),
                "Option2 Name": "Size",
                "Option2 Value": sku.get("size", ""),
                "Variant SKU": sku.get("sku_tag", ""),
                "Variant Price": sku.get("price", "0.00"),
                "Image Src": images[0] if images else "",
                "Image Alt Text": sku.get("product_name", ""),
                "Status": "active",
            })

        return output.getvalue()

    def generate_amazon_csv(self, skus: List[Dict]) -> str:
        """Generate Amazon Standard Feed CSV."""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=MARKETPLACE_CONFIGS["amazon"]["fields"])
        writer.writeheader()

        for sku in skus:
            images = sku.get("images", [])
            writer.writerow({
                "item_sku": sku.get("sku_tag", ""),
                "item_name": sku.get("product_name", ""),
                "external_product_id": sku.get("ean", ""),
                "brand_name": sku.get("brand_name", ""),
                "feed_product_type": sku.get("category", ""),
                "color_name": sku.get("color", ""),
                "size_name": sku.get("size", ""),
                "main_image_url": images[0] if images else "",
                "other_image_url1": images[1] if len(images) > 1 else "",
                "other_image_url2": images[2] if len(images) > 2 else "",
                "list_price": sku.get("price", "0.00"),
                "quantity": sku.get("quantity", 100),
                "condition_type": "New",
                "description": sku.get("description", ""),
            })

        return output.getvalue()

    def generate_zalando_json(self, skus: List[Dict]) -> str:
        """Generate Zalando JSON feed."""
        products = []
        for sku in skus:
            products.append({
                "ean": sku.get("ean", ""),
                "name": sku.get("product_name", ""),
                "brand": sku.get("brand_name", ""),
                "category": sku.get("category", ""),
                "color": sku.get("color", ""),
                "size": sku.get("size", ""),
                "price": {"amount": sku.get("price", "0.00"), "currency": "GBP"},
                "images": sku.get("images", []),
                "description": sku.get("description", ""),
                "gender": sku.get("gender", "female"),
            })
        return json.dumps({"products": products}, indent=2)

    def generate_asos_csv(self, skus: List[Dict]) -> str:
        """Generate ASOS CSV feed."""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=MARKETPLACE_CONFIGS["asos"]["fields"])
        writer.writeheader()

        for sku in skus:
            images = sku.get("images", [])
            writer.writerow({
                "ProductCode": sku.get("sku_tag", ""),
                "ProductName": sku.get("product_name", ""),
                "Brand": sku.get("brand_name", ""),
                "Category": sku.get("category", ""),
                "Colour": sku.get("color", ""),
                "Size": sku.get("size", ""),
                "Price": sku.get("price", "0.00"),
                "MainImageURL": images[0] if images else "",
                "AltImageURL1": images[1] if len(images) > 1 else "",
                "AltImageURL2": images[2] if len(images) > 2 else "",
                "Description": sku.get("description", ""),
                "Gender": sku.get("gender", "female"),
            })

        return output.getvalue()

    def generate_farfetch_json(self, skus: List[Dict]) -> str:
        """Generate Farfetch JSON feed."""
        products = []
        for sku in skus:
            products.append({
                "reference": sku.get("sku_tag", ""),
                "name": sku.get("product_name", ""),
                "designer": sku.get("brand_name", ""),
                "category": sku.get("category", ""),
                "color": sku.get("color", ""),
                "sizes": [sku.get("size", "")],
                "price": sku.get("price", "0.00"),
                "currency": "GBP",
                "images": sku.get("images", []),
                "description": sku.get("description", ""),
            })
        return json.dumps({"products": products}, indent=2)

    def generate_feed(self, marketplace: str, skus: List[Dict]) -> tuple:
        """Generate feed for specified marketplace."""
        generators = {
            "shopify": (self.generate_shopify_csv, "shopify_feed.csv", "text/csv"),
            "amazon": (self.generate_amazon_csv, "amazon_feed.csv", "text/csv"),
            "zalando": (self.generate_zalando_json, "zalando_feed.json", "application/json"),
            "asos": (self.generate_asos_csv, "asos_feed.csv", "text/csv"),
            "farfetch": (self.generate_farfetch_json, "farfetch_feed.json", "application/json"),
        }

        if marketplace not in generators:
            raise ValueError(f"Unknown marketplace: {marketplace}")

        generator, filename, content_type = generators[marketplace]
        content = generator(skus)
        return content, filename, content_type


# Singleton
marketplace_service = MarketplaceService()

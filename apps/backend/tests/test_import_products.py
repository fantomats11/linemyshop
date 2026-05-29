from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.commands.import_products import import_rows, read_product_rows
from app.db.base import Base
from app.models import InventoryBalance, Product, ProductImage, ProductVariant


CSV_CONTENT = """product_group,product_name,color,gender,category,price,sale_price,size,waist,hip,length,sku,barcode,stock,image_1,image_2,image_3,description,note,status
jeans-test,กางเกงยีนส์ทดสอบ,ยีนส์เข้ม,หญิง,กางเกงยีนส์,1750,,M,26-28,34-36,40,TEST-M,,5,https://example.com/1.jpg,https://example.com/2.jpg,,รายละเอียด,note,draft
jeans-test,กางเกงยีนส์ทดสอบ,ยีนส์เข้ม,หญิง,กางเกงยีนส์,1750,,L,28-30,36-38,40,TEST-L,TEST-L,3,https://example.com/1.jpg,https://example.com/2.jpg,,รายละเอียด,note,draft
"""


def create_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def write_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "valid_products.csv"
    csv_path.write_text(CSV_CONTENT, encoding="utf-8")
    return csv_path


def test_read_product_rows_uses_sku_when_barcode_is_blank(tmp_path: Path) -> None:
    csv_path = write_csv(tmp_path)

    rows, errors = read_product_rows(csv_path)

    assert errors == []
    assert len(rows) == 2
    assert rows[0].barcode == "TEST-M"
    assert rows[1].barcode == "TEST-L"


def test_import_rows_creates_products_variants_inventory_and_images(tmp_path: Path) -> None:
    csv_path = write_csv(tmp_path)
    rows, errors = read_product_rows(csv_path)
    session = create_session()

    stats = import_rows(session, str(csv_path), rows, errors)

    assert stats.products_created == 1
    assert stats.variants_created == 2
    assert stats.inventory_created == 2
    assert stats.images_created == 2
    assert session.scalar(select(Product).where(Product.product_group == "jeans-test"))
    assert len(session.scalars(select(ProductVariant)).all()) == 2
    assert len(session.scalars(select(InventoryBalance)).all()) == 2
    assert len(session.scalars(select(ProductImage)).all()) == 2


def test_import_rows_updates_existing_rows_without_duplicate_images(tmp_path: Path) -> None:
    csv_path = write_csv(tmp_path)
    rows, errors = read_product_rows(csv_path)
    session = create_session()

    import_rows(session, str(csv_path), rows, errors)
    stats = import_rows(session, str(csv_path), rows, errors)

    assert stats.products_updated == 1
    assert stats.variants_updated == 2
    assert stats.inventory_updated == 2
    assert stats.images_created == 0
    assert len(session.scalars(select(ProductImage)).all()) == 2

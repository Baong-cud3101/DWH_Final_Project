-- Gold: dimension sản phẩm, phân cấp sản phẩm -> subcategory -> category.
select
    row_number() over (order by product_code)   as product_key,
    product_code,
    product_name,
    subcategory,
    category
from {{ ref('silver_product') }}

union all

-- Thành viên Unknown cho mã sản phẩm không khớp danh mục
select -1, 'UNKNOWN', 'Unknown product', 'Unknown', 'Unknown'

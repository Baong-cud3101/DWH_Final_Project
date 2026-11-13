-- Silver: danh mục sản phẩm (5 ngành hàng mỹ phẩm và chăm sóc cá nhân).
select
    trim(product_code)          as product_code,
    trim(product)               as product_name,
    trim(category)              as category,
    lower(trim(subcategory))    as subcategory
from {{ source('bronze', 'product') }}

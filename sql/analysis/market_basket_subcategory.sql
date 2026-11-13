-- Phân tích giỏ hàng theo subcategory (B4.6).
-- Chuyển thể từ macro market_basket_pairs của repo tham khảo: đổi sản phẩm -> subcategory
-- và bổ sung support, confidence, lift. Chỉ xét đơn có >= 2 subcategory khác nhau khi ghép cặp.
with order_sub as (
    select distinct f.order_id, p.subcategory
    from gold.fact_sales f
    join gold.dim_product p on f.product_key = p.product_key
    where p.product_key <> -1
),
n_orders as (select count(distinct order_id) as n from order_sub),
sub_support as (
    select subcategory, count(*) as orders_with
    from order_sub group by subcategory
),
pairs as (
    select a.subcategory as antecedent, b.subcategory as consequent, count(*) as orders_both
    from order_sub a
    join order_sub b on a.order_id = b.order_id and a.subcategory <> b.subcategory
    group by 1, 2
)
select
    p.antecedent,
    p.consequent,
    p.orders_both,
    p.orders_both / n.n                                         as support,
    p.orders_both / sa.orders_with                              as confidence,
    (p.orders_both / sa.orders_with) / (sb.orders_with / n.n)   as lift
from pairs p
cross join n_orders n
join sub_support sa on p.antecedent = sa.subcategory
join sub_support sb on p.consequent = sb.subcategory
where p.orders_both >= 30
order by lift desc

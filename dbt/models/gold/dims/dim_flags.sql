-- Gold: junk dimension gom các cờ có ít giá trị thay vì để rải rác trong fact.
-- Tổ hợp: is_valid_product x is_valid_region x discount_band (6 nhóm) x is_loss = 48 dòng.
with valid_product as (select unnest([true, false]) as is_valid_product),
valid_region as (select unnest([true, false]) as is_valid_region),
loss as (select unnest([true, false]) as is_loss),
bands as (
    select * from (values
        (1, '0%'), (2, '(0%, 10%]'), (3, '(10%, 20%]'),
        (4, '(20%, 30%]'), (5, '(30%, 50%]'), (6, '> 50%')
    ) as t(discount_band_order, discount_band)
)

select
    row_number() over (
        order by vp.is_valid_product desc, vr.is_valid_region desc,
                 b.discount_band_order, l.is_loss
    )                                               as flag_key,
    vp.is_valid_product,
    vr.is_valid_region,
    b.discount_band,
    b.discount_band_order,
    b.discount_band_order >= 5                      as is_deep_discount,
    l.is_loss
from valid_product as vp
cross join valid_region as vr
cross join bands as b
cross join loss as l

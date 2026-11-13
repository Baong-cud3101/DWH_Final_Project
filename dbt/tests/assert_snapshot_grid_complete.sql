-- Kiểm tra nghiệp vụ: fact_monthly_snapshot có đủ 48 tháng x 5 market x 3 segment (= 720 ô) cộng các ô Unknown.
select count(*) as n_cells
from {{ ref('fact_monthly_snapshot') }}
where market <> 'Unknown'
having count(*) <> 48 * 5 * 3

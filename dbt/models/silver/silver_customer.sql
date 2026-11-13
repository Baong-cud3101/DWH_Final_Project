-- Silver: khách hàng đã ép kiểu và chuẩn hóa.
-- Quy tắc: gender thiếu -> 'Unknown' (giữ bản ghi); age tính theo ngày tham chiếu cố định.
with src as (
    select
        trim(customer_id)                as customer_id,
        trim(first_name)                 as first_name,
        trim(last_name)                  as last_name,
        try_cast(birth_date as date)     as birth_date,
        marital_status,
        gender,
        email_address,
        annual_income,
        education_level,
        occupation,
        home_owner
    from {{ source('bronze', 'customer') }}
)

select
    customer_id,
    first_name,
    last_name,
    birth_date,
    date_diff('year', birth_date, date '{{ var("reference_date") }}')
        - case
            when strftime(birth_date, '%m%d') > strftime(date '{{ var("reference_date") }}', '%m%d')
            then 1 else 0
          end                                                   as age,
    case marital_status when 'M' then 'Married' when 'S' then 'Single' else 'Unknown' end
                                                                as marital_status,
    case gender when 'M' then 'Male' when 'F' then 'Female' else 'Unknown' end
                                                                as gender,
    gender is null                                              as is_gender_imputed,
    lower(trim(email_address))                                  as email_address,
    try_cast(annual_income as integer)                          as annual_income,
    trim(education_level)                                       as education_level,
    trim(occupation)                                            as occupation,
    case home_owner when 'Y' then true when 'N' then false end  as is_home_owner
from src

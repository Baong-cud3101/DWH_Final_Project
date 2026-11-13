{#
  Giám sát chất lượng: sau mỗi lần dbt run/test/build, ghi kết quả từng node
  (model hoặc test) vào bảng main.audit_run_log.
#}
{% macro log_run_results(results) %}
  {% if execute %}
    {% set create_sql %}
      create schema if not exists main;
      create table if not exists main.audit_run_log (
          run_at          timestamp,
          invocation_id   varchar,
          command         varchar,
          node_id         varchar,
          resource_type   varchar,
          status          varchar,
          failures        integer,
          execution_time  double
      );
    {% endset %}
    {% do run_query(create_sql) %}
    {% if results | length > 0 %}
      {% set rows = [] %}
      {% for r in results %}
        {% set row %}
          (current_timestamp, '{{ invocation_id }}', '{{ flags.WHICH }}',
           '{{ r.node.unique_id }}', '{{ r.node.resource_type }}', '{{ r.status }}',
           {{ r.failures if r.failures is not none else 'null' }},
           {{ r.execution_time | round(3) }})
        {% endset %}
        {% do rows.append(row) %}
      {% endfor %}
      {% set insert_sql %}
        insert into main.audit_run_log values {{ rows | join(',') }};
      {% endset %}
      {% do run_query(insert_sql) %}
    {% endif %}
  {% endif %}
{% endmacro %}

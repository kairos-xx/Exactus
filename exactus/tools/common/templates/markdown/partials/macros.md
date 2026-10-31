{% macro cell(block, key) %}{% if block.get(key) is none %}N/A{% else %}{{ block.get(key) | md_cell }}{% endif %}{% endmacro %}
{% macro bullets(items, reason) %}{% if items %}{% for item in (items if items is sequence and items is not string else [items]) %}- {{ item | md_code }}{{ "\n" if not loop.last }}{% endfor %}{% else %}N/A — {{ reason }}.{% endif %}{% endmacro %}

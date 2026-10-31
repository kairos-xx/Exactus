# Hello, {{ name }}

{% for item in items -%}
- {{ item.rank }}. {{ item.title }}
{% endfor %}

{% macro general_text_cleaning(column_name) %}
    TRANSLATE(
        BTRIM(UPPER({{column_name}})),
        'ÁÀÃÂÄÉÈÊËÍÌÎÏÓÒÕÔÖÚÙÛÜÇ',
        'AAAAAEEEEIIIIOOOOOUUUUC'
    )
{% endmacro %}

{% macro left_minus_x(column_name,x) %}
    left({{column_name}},len),
{% endmacro %}
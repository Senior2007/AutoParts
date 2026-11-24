"""Curated trace links. Test identifiers and requirement keys are validated before export."""

PYTEST = {
    'FR-01': 'catalog_hides_inactive_parts public_parts_page_available',
    'FR-02': 'catalog_search part_list_search_without_javascript bug4_cyrillic_search_ignores_case',
    'FR-03': 'part_list_filter_by_type bug1_catalog_with_text_type_filter_does_not_crash',
    'FR-04': 'catalog_sort part_list_sort_by_price',
    'FR-05': 'news_detail_and_part_detail_are_available bug3_deleted_part_page_is_not_found',
    'FR-06': 'cart_add_keeps_quantity_within_limits add_part_to_cart add_is_limited_by_stock out_of_stock_part_is_not_added',
    'FR-07': ('cart_remove_deletes_only_given_position cart_remove_missing_position_does_not_fail '
              'cart_clear_empties_session empty_cart_page_available increase_and_decrease_quantity '
              'decrease_last_item_removes_it increase_above_stock_is_blocked remove_and_clear_cart cart_page_shows_total'),
    'FR-08': 'cart_drops_parts_that_are_no_longer_available deleted_part_is_dropped_from_cart deactivated_part_is_dropped_from_cart',
    'FR-09': ('guest_is_sent_to_login_and_no_order_created checkout_redirects_when_cart_is_empty checkout_requires_login '
              'checkout_requires_client_profile checkout_page_available_with_items checkout_with_stale_cart_does_not_create_empty_order '
              'guest_cannot_pay_and_no_order_is_created cart_offers_login_to_guest'),
    'FR-10': ('checkout_form_valid_data_is_accepted checkout_form_rejects_invalid_input checkout_form_erip_does_not_require_card '
              'courier_delivery_requires_address card_payment_requires_card_fields card_number_must_contain_sixteen_digits '
              'delivery_date_cannot_be_in_the_past valid_form_without_card'),
    'FR-11': ('promo_is_current promo_clean_rejects_end_before_start promo_code_is_applied_through_whole_scenario '
              'promo_code_reduces_order_total unknown_promo_code_is_rejected'),
    'FR-12': ('card_payment_moves_order_from_cart_to_paid successful_payment_creates_order_and_clears_cart '
              'payment_decreases_stock_exactly_once payment_of_whole_stock_succeeds '
              'order_pay_writes_sales_and_decreases_stock paid_order_appears_in_profile'),
    'FR-13': 'deferred_payment_order_waits_then_becomes_paid pay_fails_when_stock_ran_out_and_order_stays_new bug5_success_page_does_not_say_paid_for_new_order',
    'FR-14': 'new_order_can_be_canceled finished_order_does_not_change_state cancel_new_order_sets_canceled_status cancel_is_forbidden_for_finished_order pay_is_forbidden_for_finished_order',
    'FR-15': 'other_user_cannot_change_order paid_order_is_linked_to_user_and_client order_success_is_hidden_from_other_user',
    'FR-16': ('registration_creates_user_and_client_profile registration_rejects_invalid_data registration_post_succeeds_with_csrf '
              'validate_adult_boundaries validate_adult_rejects_underage registration_form_rejects_wrong_phone registration_form_rejects_invalid_email'),
    'FR-17': 'review_create_requires_login_and_saves_for_user',
    'FR-18': 'staff_soft_deletes_part client_cannot_create_part staff_crud_is_forbidden_for_regular_user staff_can_soft_delete_part',
    'FR-19': 'stats_available_only_for_staff stats_and_chart_for_staff_only',
    'FR-20': 'parts_api_hides_sku_for_client_and_shows_for_staff api_requires_login',
    'FR-21': 'external_apis_page_shows_data_from_services external_apis_page_survives_service_failure external_api_page_uses_two_values',
    'FR-22': ('vin_topic_requires_vin short_vin_is_rejected wrong_phone_is_rejected valid_feedback_is_accepted '
              'feedback_view_saves_nothing_but_redirects invalid_feedback_view_renders_errors bug6_feedback_accepts_next_model_year'),
    'NFR-02': ('state_change_requires_post cart_add_rejects_get_request registration_post_succeeds_with_csrf '
               'registration_creates_user_and_client_profile bug2_cart_add_does_not_redirect_to_external_site '
               'sku_hidden_for_regular_user sku_visible_for_staff'),
    'NFR-03': ('safe_api_get_returns_json_on_success safe_api_get_returns_fallback_on_error order_pay_without_items_is_rejected '
               'order_pay_writes_sales_and_decreases_stock pay_fails_when_stock_ran_out_and_order_stays_new '
               'external_apis_page_survives_service_failure'),
    'NFR-04': ('phone_validator_accepts_belarus_format phone_validator_rejects_wrong_format email_validator validate_not_future_rejects_tomorrow '
               'checkout_form_rejects_invalid_input invalid_feedback_view_renders_errors bug1_catalog_with_text_type_filter_does_not_crash '
               'cart_with_broken_session_value_starts_empty'),
    'NFR-06': 'invalid_payment_shows_error_summary_at_top',
    'BT-2': 'sale_decreases_stock_in_db sale_more_than_stock_is_rejected_and_stock_unchanged',
    'BT-4': 'promo_applies_to_part_by_product_type sale_with_valid_promo_applies_discount sale_rejects_promo_for_wrong_product_type',
}

# Indexes refer to the recorded Postman execution report, not inferred by URL alone.
POSTMAN = {
    'FR-02': '8 78', 'FR-03': '27 28', 'FR-04': '8 26',
    'FR-05': '9 10 86', 'FR-06': '31 37 40 53 59 91',
    'FR-07': '13 32 33 34 35 36 38 39', 'FR-09': '1 2 3 30 41 90 92',
    'FR-10': '42 60', 'FR-11': '43 58 60 61', 'FR-12': '60 61 62',
    'FR-13': '44 45 48 49 50 54 55', 'FR-14': '51 52 56 57', 'FR-15': '46',
    'FR-16': '16 17 18 19', 'FR-17': '4 63 64 65 66 67',
    'FR-18': '29 79 80 81 82 83 84 85', 'FR-19': '5 75 76', 'FR-20': '6 25 50 77',
    'FR-21': '12', 'FR-22': '68 69 70 71',
    'NFR-02': '1 2 3 4 5 6 14 15 19 20 21 22 23 24 29 46 47 72 73 74 87 88 89 93',
    'NFR-04': '7 17 22 28 42 43 65 69',
}

BROWSER = {
    'UI-01': 'FR-16',
    'UI-02': 'FR-02 FR-06 FR-07',
    'UI-03': 'FR-09 FR-13',
    'UI-04': 'FR-13 FR-14',
    'UI-05': 'FR-09 NFR-02',
    'LAY-01': 'NFR-06',
    'LAY-02': 'NFR-06',
    'LAY-03': 'NFR-06',
    'LAY-04': 'FR-02 NFR-06',
    'LAY-05': 'NFR-06',
}

SECURITY = {
    'SEC-01': 'FR-09 FR-17 FR-19 FR-20 NFR-02',
    'SEC-02': 'FR-15 NFR-02',
    'SEC-03': 'NFR-02',
    'SEC-04': '',
    'SEC-05': '',
    'SEC-06': 'FR-21 NFR-03',
    'SEC-07': '',
    'SEC-08': 'FR-16 NFR-02',
    'PERF-01': 'NFR-01',
}

USE_CASES = {
    'UC-1': 'FR-01 FR-02 FR-03 FR-04 FR-05',
    'UC-2': 'FR-06 FR-07 FR-08',
    'UC-3': 'FR-09 FR-10 FR-11 FR-12 FR-13 FR-15',
    'UC-4': 'FR-14 FR-15',
    'UC-5': 'FR-16',
    'UC-6': 'FR-17',
    'UC-7': 'FR-18',
    'UC-8': 'FR-19',
    'UC-9': 'FR-21',
}

BUSINESS = {
    'BT-1': 'UC-1 UC-2 UC-3',
    'BT-2': 'FR-12 FR-13',
    'BT-3': 'UC-7 UC-8',
    'BT-4': 'FR-11',
}

PARTIAL = {
    'BT-2': 'Есть проверки одиночных операций и атомарности, конкурентные оплаты не выполнены.',
    'BT-4': 'Ограничение промокода по типам проверено в старом сценарии покупки; смешанная корзина требует отдельного теста.',
    'NFR-05': 'SQLite запускается командой docs.qa. Отдельного тест-кейса запуска Docker/PostgreSQL нет. Сверка ЛР1 была ручной.',
    'NFR-06': 'Валидатор запущен на четырёх страницах, совместимость измерена на заданной выборке.',
}

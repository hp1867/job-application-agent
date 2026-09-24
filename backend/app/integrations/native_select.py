"""One native dropdown action using an exact verified label; no fallback retries."""
async def select_verified_label(page,selector,answer,check_context):
    if not isinstance(answer,str) or not answer.strip():raise ValueError('Verified text answer required')
    control=page.locator(selector)
    if await control.count()!=1:raise ValueError('Dropdown must be unambiguous')
    if await control.get_attribute('multiple') is not None:raise ValueError('Multiple selection requires manual review')
    options=control.locator('option');count=await options.count()
    if not 0<count<=500:raise ValueError('Dropdown options absent or exceed safe bound')
    choices=[]
    for index in range(count):
        option=options.nth(index);label=await option.get_attribute('label')
        if label is None:label=await option.text_content()
        if (label or '').strip()==answer.strip():
            value=await option.get_attribute('value')
            if value is None or await option.is_disabled():raise ValueError('Matching option disabled or missing explicit value')
            choices.append(value)
    if len(choices)!=1:raise ValueError('Exactly one option must match the verified answer label')
    check_context()
    selected=await page.select_option(selector,value=choices[0],timeout=15000)
    if selected!=choices or await page.input_value(selector)!=choices[0]:
        raise ValueError('Dropdown selection not confirmed; do not retry automatically')
    return {'selected':True,'requires_final_form_observation':True}

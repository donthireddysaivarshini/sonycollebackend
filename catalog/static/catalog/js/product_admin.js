/**
 * Sony Feeding Kurtis - Product Admin Dynamic Assistant
 * Dynamically updates variant inline hints and defaults when feeding_config changes.
 */
document.addEventListener('DOMContentLoaded', function () {
    const feedingSelect = document.getElementById('id_feeding_config');
    if (!feedingSelect) return;

    // Create a live status indicator banner above the variant inline section
    const banner = document.createElement('div');
    banner.id = 'feeding-config-variant-banner';
    banner.style.padding = '10px 14px';
    banner.style.marginBottom = '12px';
    banner.style.borderRadius = '6px';
    banner.style.fontSize = '13px';
    banner.style.fontWeight = '500';
    banner.style.transition = 'all 0.25s ease';

    function updateVariantAssistance() {
        const val = feedingSelect.value;
        const variantsGroup = document.querySelector('#variants-group, .tabular.inline-related');

        if (!variantsGroup) return;

        if (!document.getElementById('feeding-config-variant-banner')) {
            const heading = variantsGroup.querySelector('h2') || variantsGroup.firstChild;
            if (heading) {
                heading.parentNode.insertBefore(banner, heading.nextSibling);
            }
        }

        if (val === 'feeding-only') {
            banner.style.backgroundColor = '#ECFDF5';
            banner.style.border = '1px solid #A7F3D0';
            banner.style.color = '#065F46';
            banner.innerHTML = '🍼 <strong>Feeding Only:</strong> Every variant row below represents a feeding garment (clothing type: <em>Feeding</em>). Non-Feeding variants will be rejected.';
        } else if (val === 'none') {
            banner.style.backgroundColor = '#F3F4F6';
            banner.style.border = '1px solid #E5E7EB';
            banner.style.color = '#374151';
            banner.innerHTML = '👗 <strong>Standard / Non-Feeding:</strong> This product does not feature feeding zippers (clothing type: <em>Standard</em>).';
        } else {
            banner.style.backgroundColor = '#FAF5FC';
            banner.style.border = '1px solid #E9D5FF';
            banner.style.color = '#552058';
            banner.innerHTML = '✨ <strong>Both Feeding & Non-Feeding:</strong> You can add both <em>Feeding</em> and <em>Non-Feeding</em> rows for this product. Customers will toggle between them on the product page.';
        }

        // Auto-adjust default clothing type for empty or new inline selects
        const clothingTypeSelects = document.querySelectorAll('select[name$="-clothing_type"]');
        clothingTypeSelects.forEach((sel) => {
            if (val === 'feeding-only' && (!sel.value || sel.value === 'Standard' || sel.value === 'Non-Feeding')) {
                sel.value = 'Feeding';
            } else if (val === 'none' && (!sel.value || sel.value === 'Feeding' || sel.value === 'Non-Feeding')) {
                sel.value = 'Standard';
            }
        });
    }

    feedingSelect.addEventListener('change', updateVariantAssistance);
    updateVariantAssistance();

    // Listen to dynamically added inline rows
    document.addEventListener('formset:added', function () {
        updateVariantAssistance();
    });
});

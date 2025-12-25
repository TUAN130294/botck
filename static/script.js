// Utility functions for the web app

// Auto-hide flash messages after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    const flashMessages = document.querySelectorAll('.flash');
    flashMessages.forEach(function(flash) {
        setTimeout(function() {
            flash.style.opacity = '0';
            flash.style.transition = 'opacity 0.3s';
            setTimeout(function() {
                flash.remove();
            }, 300);
        }, 5000);
    });
});

// Format number with commas
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Confirm before delete
function confirmDelete(message) {
    return confirm(message || 'Bạn có chắc muốn xóa?');
}

// Show loading state
function showLoading(element) {
    if (element) {
        element.disabled = true;
        element.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang xử lý...';
    }
}

// Hide loading state
function hideLoading(element, originalText) {
    if (element) {
        element.disabled = false;
        element.innerHTML = originalText;
    }
}

// Handle form errors
function showError(message) {
    alert('Lỗi: ' + message);
}

// Handle success
function showSuccess(message) {
    alert('Thành công: ' + message);
}

// Smooth scroll
function smoothScrollTo(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}


from functools import wraps
from flask import abort, session, current_app, flash, redirect, url_for
from .models import User
from .col import login_collection, login_cust_collection

def require_role(required_role, redirect_on_failure=True):
    """
    Decorator to require a specific role for accessing a route.
    
    Args:
        required_role (str): The role required to access the route
        redirect_on_failure (bool): Whether to redirect or abort with 403 on failure
    
    Returns:
        function: The decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask_security import current_user
            
            # Check if user is authenticated
            if not current_user.is_authenticated:
                if redirect_on_failure:
                    flash("Please log in to access this page.", "warning")
                    return redirect(url_for('new_auth.index'))
                else:
                    abort(403)
            
            # Check if user has required role
            if not current_user.has_role(required_role):
                if redirect_on_failure:
                    flash("You don't have permission to access this page.", "danger")
                    # Redirect to appropriate dashboard
                    if current_user.has_role('admin'):
                        return redirect(url_for('dashboard'))
                    elif current_user.has_role('customer'):
                        return redirect(url_for('customer.customer_form'))
                    else:
                        return redirect(url_for('new_auth.index'))
                else:
                    abort(403)
            
            # For admin roles, check if they're a super admin for certain actions
            if required_role == 'admin':
                # Check if this is a super admin only action
                if hasattr(func, '_super_admin_only') and func._super_admin_only:
                    # Check if user is super admin
                    user_doc = login_collection.find_one({'email': current_user.email})
                    if not user_doc or not user_doc.get('is_super_admin', False):
                        if redirect_on_failure:
                            flash("Only super administrators can access this page.", "danger")
                            return redirect(url_for('dashboard'))
                        else:
                            abort(403)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def super_admin_required(func):
    """
    Decorator to require super admin privileges for a route.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        from flask_security import current_user
        
        # Check if user is authenticated
        if not current_user.is_authenticated:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('new_auth.index'))
        
        # Check if user has admin role
        if not current_user.has_role('admin'):
            flash("Only administrators can access this page.", "danger")
            return redirect(url_for('new_auth.index'))
        
        # Check if user is super admin in session (set during login)
        if not session.get('is_super_admin', False):
            flash("Only super administrators can access this page.", "danger")
            return redirect(url_for('dashboard'))
        
        # Double-check in database that user is actually super admin
        user_doc = login_collection.find_one({'email': current_user.email})
        if not user_doc or not user_doc.get('is_super_admin', False):
            flash("Only super administrators can access this page.", "danger")
            return redirect(url_for('dashboard'))
        
        return func(*args, **kwargs)
    return wrapper

def require_admin(func):
    """
    Decorator to require admin role for a route.
    """
    return require_role('admin', redirect_on_failure=True)(func)

def require_customer(func):
    """
    Decorator to require customer role for a route.
    """
    return require_role('customer', redirect_on_failure=True)(func)

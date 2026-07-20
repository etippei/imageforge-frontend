// ============================================
// 前端公共JS - 包含认证、API调用、使用统计
// ============================================

// ============================================
// API配置 - 指向 Cloudflare Worker
// ============================================
const API_BASE = 'https://cloakimg-api.etiplpl.workers.dev/api';

// ---------- 用户认证 ----------
async function apiRequest(endpoint, options = {}) {
    const token = localStorage.getItem('forge_token');
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    const response = await fetch(API_BASE + endpoint, {
        ...options,
        headers: headers,
        body: options.body ? JSON.stringify(options.body) : undefined
    });
    
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || 'Request failed');
    }
    return data;
}

async function register(email, password) {
    return await apiRequest('/auth/register', {
        method: 'POST',
        body: { email, password }
    });
}

async function login(email, password) {
    const result = await apiRequest('/auth/login', {
        method: 'POST',
        body: { email, password }
    });
    if (result.token) {
        localStorage.setItem('forge_token', result.token);
        localStorage.setItem('forge_user', JSON.stringify(result.user));
    }
    return result;
}

function logout() {
    localStorage.removeItem('forge_token');
    localStorage.removeItem('forge_user');
    window.location.reload();
}

async function forgotPassword(email) {
    return await apiRequest('/auth/forgot-password', {
        method: 'POST',
        body: { email }
    });
}

async function resetPassword(token, newPassword) {
    return await apiRequest('/auth/reset-password', {
        method: 'POST',
        body: { token, newPassword }
    });
}

async function changePassword(currentPassword, newPassword) {
    return await apiRequest('/auth/change-password', {
        method: 'POST',
        body: { current_password: currentPassword, new_password: newPassword }
    });
}

async function getUsage() {
    return await apiRequest('/usage', { method: 'GET' });
}

// ---------- 文件上传到VPS ----------
async function uploadToVPS(endpoint, file, extraData = {}) {
    const formData = new FormData();
    formData.append('file', file);
    Object.keys(extraData).forEach(key => {
        formData.append(key, extraData[key]);
    });
    
    const token = localStorage.getItem('forge_token');
    const response = await fetch(API_BASE + endpoint, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`
        },
        body: formData
    });
    
    const data = await response.json();
    if (!response.ok) {
        if (response.status === 429) {
            throw new Error(`Daily limit reached. ${data.remaining || 0} remaining.`);
        }
        throw new Error(data.error || 'Upload failed');
    }
    return data;
}

// ---------- 轮询结果 ----------
async function pollResult(taskId, maxAttempts = 60, interval = 2000) {
    const token = localStorage.getItem('forge_token');
    for (let i = 0; i < maxAttempts; i++) {
        const response = await fetch(`${API_BASE}/result/${taskId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        const data = await response.json();
        
        if (data.status === 'completed') {
            return data;
        } else if (data.status === 'failed') {
            throw new Error(data.error || 'Processing failed');
        }
        
        await new Promise(r => setTimeout(r, interval));
    }
    throw new Error('Processing timeout');
}

// ---------- 工具函数 ----------
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

function downloadBase64(base64String, filename, mimeType = 'image/png') {
    const link = document.createElement('a');
    link.download = filename;
    link.href = `data:${mimeType};base64,${base64String}`;
    link.click();
}

function getToolDisplayName(toolType) {
    const map = {
        'upscaler': 'AI Upscaler',
        'rembg': 'Background Remover',
        'compressor': 'Compressor',
        'convert': 'PNG to JPG',
        'resize': 'Resize',
        'idphoto': 'ID Photo Maker'
    };
    return map[toolType] || toolType;
}

// ---------- 显示使用次数 ----------
function displayUsageInfo(containerId, toolType) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    const user = JSON.parse(localStorage.getItem('forge_user'));
    if (!user) {
        container.innerHTML = `
            <div style="background: #fef3c7; padding: 10px 16px; border-radius: 12px; font-size: 0.9rem; display: flex; justify-content: space-between; align-items: center;">
                <span>🔒 <a href="#" id="loginPromptLink" style="color: #2563eb; font-weight: 600;">Sign in</a> to use this tool</span>
                <span style="color: #92400e; font-size: 0.8rem;">Free: 3/day · Pro: Unlimited</span>
            </div>
        `;
        document.getElementById('loginPromptLink')?.addEventListener('click', (e) => {
            e.preventDefault();
            openAuthModal('login');
        });
        return;
    }
    
    getUsage().then(usage => {
        const tool = usage.tools[toolType];
        if (!tool) return;
        
        const isPro = tool.isPro;
        const used = tool.used;
        const limit = tool.limit;
        const remaining = tool.remaining;
        const percent = limit > 0 ? (used / limit) * 100 : 0;
        
        // 检查是否有额外额度（24小时套餐购买后，会有 extra_credits）
        const extraCredits = usage.extra_credits || 0;
        const totalRemaining = remaining + extraCredits;
        
        let color = '#2563eb';
        if (percent > 80) color = '#ef4444';
        else if (percent > 50) color = '#f59e0b';
        
        let bottomText = '';
        if (isPro) {
            bottomText = '♾️ Unlimited';
        } else if (extraCredits > 0) {
            bottomText = `⚡ ${totalRemaining} remaining (${extraCredits} extra credits)`;
        } else if (remaining <= 0) {
            bottomText = `<a href="pricing.html#hourly" style="color: #f59e0b; font-weight: 600;">⬇️ Get 5 extra for $1.99</a>`;
        } else {
            bottomText = `${remaining} remaining today`;
        }
        
        container.innerHTML = `
            <div style="background: #f1f5f9; padding: 12px 16px; border-radius: 12px; font-size: 0.9rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                    <span>
                        ${isPro ? '⭐ Pro' : extraCredits > 0 ? '⚡ Extra Credits' : '📊 Free'}
                        <strong>${getToolDisplayName(toolType)}</strong>
                    </span>
                    <span>
                        ${isPro ? '♾️ Unlimited' : `${used} / ${limit} used`}
                        ${extraCredits > 0 ? ' + ⚡' + extraCredits : ''}
                        ${!isPro && remaining <= 2 && extraCredits === 0 ? ' ⚠️' : ''}
                    </span>
                </div>
                ${!isPro ? `
                    <div style="width: 100%; height: 6px; background: #e2e8f0; border-radius: 4px; margin-top: 8px; overflow: hidden;">
                        <div style="width: ${Math.min(100, percent)}%; height: 100%; background: ${color}; border-radius: 4px; transition: width 0.3s;"></div>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-top: 4px; font-size: 0.75rem; color: #64748b;">
                        <span>${bottomText}</span>
                        ${!isPro && remaining === 0 && extraCredits === 0 ? '<a href="pricing.html" style="color: #f59e0b; font-weight: 600;">Try 24h for $1.99 →</a>' : ''}
                    </div>
                ` : ''}
            </div>
        `;
    }).catch(() => {
        container.innerHTML = `
            <div style="background: #fef3c7; padding: 10px 16px; border-radius: 12px; font-size: 0.9rem; color: #92400e;">
                ⚠️ Could not load usage data
            </div>
        `;
    });
}

// ---------- 渲染登录状态UI ----------
function renderAuthWidget() {
    const widget = document.getElementById('authWidget');
    if (!widget) return;
    
    const user = JSON.parse(localStorage.getItem('forge_user'));
    if (user) {
        const planLabel = user.plan === 'pro' ? 'PRO ⭐' : 'FREE';
        widget.innerHTML = `
            <div class="user-greeting">
                <i class="fas fa-user-circle"></i> ${user.email.split('@')[0]} 
                <span class="plan-badge">${planLabel}</span>
            </div>
            <a href="account.html" class="btn btn-ghost" style="text-decoration:none;">
                <i class="fas fa-user"></i> Account
            </a>
            <button class="btn btn-ghost" id="logoutBtn"><i class="fas fa-sign-out-alt"></i></button>
        `;
        document.getElementById('logoutBtn')?.addEventListener('click', logout);
    } else {
        widget.innerHTML = `
            <button class="btn btn-outline" id="loginBtn"><i class="fas fa-key"></i> Sign in</button>
            <button class="btn btn-primary" id="signupBtn"><i class="fas fa-user-plus"></i> Get started</button>
        `;
        document.getElementById('loginBtn')?.addEventListener('click', () => openAuthModal('login'));
        document.getElementById('signupBtn')?.addEventListener('click', () => openAuthModal('signup'));
    }
}

// ---------- 认证弹窗 ----------
function openAuthModal(mode) {
    const modal = document.createElement('div');
    modal.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center;
        z-index: 1000;
    `;
    
    const isLogin = mode === 'login';
    modal.innerHTML = `
        <div style="background: white; border-radius: 24px; padding: 40px; max-width: 420px; width: 90%; box-shadow: 0 20px 60px rgba(0,0,0,0.3); position: relative;">
            <div style="text-align: center;">
                <i class="fas fa-user-circle" style="font-size: 48px; color: #2563eb;"></i>
                <h2 style="margin: 12px 0 4px;">${isLogin ? 'Welcome Back' : 'Create Account'}</h2>
                <p style="color: #64748b; font-size: 0.9rem;">${isLogin ? 'Sign in to access all tools' : 'Start using AI image tools for free'}</p>
            </div>
            <form id="authForm" style="margin-top: 24px;">
                <div style="margin-bottom: 16px;">
                    <label style="display: block; font-size: 0.85rem; font-weight: 500; margin-bottom: 4px;">Email</label>
                    <input type="email" id="authEmail" placeholder="you@example.com" style="width: 100%; padding: 12px; border: 1px solid #cbd5e1; border-radius: 12px; font-size: 1rem;">
                </div>
                <div style="margin-bottom: 16px;">
                    <label style="display: block; font-size: 0.85rem; font-weight: 500; margin-bottom: 4px;">Password</label>
                    <input type="password" id="authPassword" placeholder="${isLogin ? 'Enter password' : 'Min 6 characters'}" style="width: 100%; padding: 12px; border: 1px solid #cbd5e1; border-radius: 12px; font-size: 1rem;">
                </div>
                ${isLogin ? `
                    <div style="text-align: right; margin-bottom: 16px;">
                        <a href="forgot-password.html" style="font-size: 0.8rem; color: #2563eb; text-decoration: none; font-weight: 500;">Forgot password?</a>
                    </div>
                ` : ''}
                <button type="submit" style="width: 100%; padding: 14px; background: linear-gradient(135deg, #2563eb, #7c3aed); color: white; border: none; border-radius: 40px; font-size: 1rem; font-weight: 600; cursor: pointer;">
                    ${isLogin ? 'Sign In' : 'Create Account'}
                </button>
                <div style="text-align: center; margin-top: 16px; font-size: 0.85rem; color: #64748b;">
                    ${isLogin ? "Don't have an account? " : "Already have an account? "}
                    <a href="#" id="switchAuthMode" style="color: #2563eb; text-decoration: none; font-weight: 500;">
                        ${isLogin ? 'Sign up' : 'Sign in'}
                    </a>
                </div>
            </form>
            <div id="authMessage" style="margin-top: 12px; font-size: 0.85rem; text-align: center;"></div>
            <button id="closeAuthModal" style="position: absolute; top: 16px; right: 16px; background: none; border: none; font-size: 20px; cursor: pointer; color: #94a3b8;">×</button>
        </div>
    `;
    document.body.appendChild(modal);
    
    modal.querySelector('#closeAuthModal').addEventListener('click', () => modal.remove());
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });
    
    modal.querySelector('#switchAuthMode').addEventListener('click', (e) => {
        e.preventDefault();
        modal.remove();
        openAuthModal(isLogin ? 'signup' : 'login');
    });
    
    modal.querySelector('#authForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = modal.querySelector('#authEmail').value;
        const password = modal.querySelector('#authPassword').value;
        const messageEl = modal.querySelector('#authMessage');
        const submitBtn = modal.querySelector('button[type="submit"]');
        
        try {
            if (isLogin) {
                const result = await login(email, password);
                messageEl.innerHTML = '✅ Login successful!';
                messageEl.style.color = '#22c55e';
                setTimeout(() => {
                    modal.remove();
                    window.location.reload();
                }, 1000);
            } else {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-pulse"></i> Creating account...';
                
                const result = await register(email, password);
                
                messageEl.innerHTML = `
                    <div style="background: #dbeafe; border-radius: 12px; padding: 14px; text-align: left;">
                        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
                            <span style="font-size: 1.5rem;">📧</span>
                            <span style="font-weight: 600; color: #1e40af;">Verification email sent!</span>
                        </div>
                        <p style="color: #1e3a5f; font-size: 0.85rem; margin: 4px 0;">
                            We've sent a verification link to <strong>${email}</strong>.
                        </p>
                        <p style="color: #1e3a5f; font-size: 0.8rem; margin: 4px 0;">
                            ⏳ Please check your inbox and click the link to activate your account.
                        </p>
                        <p style="color: #6b7280; font-size: 0.75rem; margin: 8px 0 0 0;">
                            💡 Didn't see the email? Check your <strong>Spam</strong> folder.
                        </p>
                    </div>
                `;
                messageEl.style.color = '#1e40af';
                
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'Create Account';
                
                setTimeout(() => {
                    if (document.body.contains(modal)) {
                        modal.remove();
                    }
                }, 8000);
            }
        } catch (error) {
            messageEl.innerHTML = `❌ ${error.message || (isLogin ? 'Login failed' : 'Registration failed')}`;
            messageEl.style.color = '#ef4444';
            if (!isLogin) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'Create Account';
            }
        }
    });
}

window.ForgeAuth = {
    login,
    register,
    logout,
    forgotPassword,
    resetPassword,
    changePassword,
    getUsage,
    uploadToVPS,
    pollResult,
    displayUsageInfo,
    openAuthModal,
    renderAuthWidget,
    formatFileSize,
    downloadBase64,
    getToolDisplayName,
    currentUser: () => JSON.parse(localStorage.getItem('forge_user'))
};

document.addEventListener('DOMContentLoaded', function() {
    if (typeof window.ForgeAuth !== 'undefined' && window.ForgeAuth.renderAuthWidget) {
        window.ForgeAuth.renderAuthWidget();
    }
});
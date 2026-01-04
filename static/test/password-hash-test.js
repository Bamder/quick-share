/**
 * 密码哈希测试用例
 * 用于测试密码哈希功能是否正常工作
 */

// 导入密码哈希函数
import { hashPassword } from '../service/user-service.js';

// 测试用例数组
const testCases = [
    {
        name: '简单密码',
        password: '123456'
    },
    {
        name: '中等复杂度密码',
        password: 'Password123'
    },
    {
        name: '强密码',
        password: 'P@ssw0rd!2024'
    },
    {
        name: '短密码',
        password: 'a1b2c3'
    },
    {
        name: '长密码',
        password: 'ThisIsAVeryLongPasswordWithNumbers123AndSpecialCharacters!@#'
    }
];

/**
 * 运行所有测试用例
 */
export async function runPasswordHashTests() {
    console.log('\n=== 密码哈希测试开始 ===');
    console.log('测试时间:', new Date().toLocaleString());
    console.log('测试用例数量:', testCases.length);
    console.log('========================\n');
    
    let passedTests = 0;
    let failedTests = 0;
    
    // 遍历所有测试用例
    for (let i = 0; i < testCases.length; i++) {
        const testCase = testCases[i];
        const testNumber = i + 1;
        
        console.log(`测试用例 ${testNumber}: ${testCase.name}`);
        console.log(`密码: ${testCase.password}`);
        console.log(`密码长度: ${testCase.password.length} 字符`);
        
        try {
            // 执行密码哈希
            const startTime = performance.now();
            const hashedPassword = await hashPassword(testCase.password);
            const endTime = performance.now();
            const duration = endTime - startTime;
            
            // 验证哈希结果
            if (hashedPassword && typeof hashedPassword === 'string' && hashedPassword.length === 64) {
                console.log(`✅ 测试通过`);
                console.log(`哈希结果: ${hashedPassword}`);
                console.log(`哈希长度: ${hashedPassword.length} 字符`);
                console.log(`执行时间: ${duration.toFixed(2)} ms`);
                passedTests++;
            } else {
                console.log(`❌ 测试失败: 哈希结果无效`);
                console.log(`哈希结果: ${hashedPassword}`);
                console.log(`哈希长度: ${hashedPassword ? hashedPassword.length : 'N/A'} 字符`);
                failedTests++;
            }
        } catch (error) {
            console.log(`❌ 测试失败: ${error.message}`);
            console.error(error);
            failedTests++;
        }
        
        console.log('------------------------\n');
    }
    
    // 输出测试结果统计
    console.log('=== 密码哈希测试结束 ===');
    console.log(`总测试用例: ${testCases.length}`);
    console.log(`通过测试: ${passedTests}`);
    console.log(`失败测试: ${failedTests}`);
    console.log(`测试通过率: ${((passedTests / testCases.length) * 100).toFixed(2)}%`);
    console.log('========================\n');
    
    return {
        total: testCases.length,
        passed: passedTests,
        failed: failedTests,
        successRate: (passedTests / testCases.length) * 100
    };
}

// 如果直接运行此文件，则执行测试
if (typeof window !== 'undefined') {
    // 在浏览器环境中运行
    window.runPasswordHashTests = runPasswordHashTests;
    console.log('密码哈希测试函数已加载，可在控制台中运行 runPasswordHashTests() 执行测试');
} else {
    // 在Node.js环境中运行
    runPasswordHashTests();
}

#!/bin/bash

# 增强版系统压力测试脚本
# 使用方法：chmod +x enhanced_stress_test.sh && ./enhanced_stress_test.sh

# 配置参数
TARGET_URL="http://39.96.160.217/"  # 请修改为你的待测服务地址
REPORT_FILE="detailed_stress_report.log"
CONCURRENT_USERS=20
TOTAL_REQUESTS=50

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 初始化日志文件
: > $REPORT_FILE

# 辅助函数：安全计算
safe_calc() {
    echo "scale=2; $1" | bc 2>/dev/null || echo "0"
}

# 辅助函数：获取纯数字系统指标
get_system_metrics() {
    local prefix=$1
    local cpu_usage=$(top -bn1 | grep "%Cpu(s)" | head -1 | awk '{print $2}' | cut -d'.' -f1)
    local mem_usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    local load_1min=$(uptime | awk -F'load average:' '{print $2}' | awk -F, '{print $1}' | sed 's/ //g')
    local http_conn=$(netstat -an 2>/dev/null | grep :80 | wc -l)

    # 直接记录到文件
    {
        echo "${prefix}CPU使用率: ${cpu_usage}%"
        echo "${prefix}内存使用率: ${mem_usage}%"
        echo "${prefix}系统负载(1分钟): ${load_1min}"
        echo "${prefix}HTTP连接数: ${http_conn}"
    } >> $REPORT_FILE

    # 返回指标用于后续计算
    echo "$cpu_usage $mem_usage $load_1min $http_conn"
}

# 主测试函数
run_comprehensive_test() {
    echo -e "${GREEN}=== 系统压力测试开始 ===${NC}" | tee -a $REPORT_FILE
    echo "测试时间: $(date)" >> $REPORT_FILE
    echo "目标URL: $TARGET_URL" >> $REPORT_FILE
    echo "并发数: $CONCURRENT_USERS, 总请求数: $TOTAL_REQUESTS" >> $REPORT_FILE

    # 1. 压测前系统状态
    echo -e "\n${BLUE}--- 压测前系统基准 ---${NC}" >> $REPORT_FILE
    BEFORE_METRICS=$(get_system_metrics "压测前_")

    # 2. 执行Web压力测试 (ab)
    echo -e "\n${YELLOW}>>> 启动Web压力测试...${NC}" >> $REPORT_FILE
    ab -k -c $CONCURRENT_USERS -n $TOTAL_REQUESTS "$TARGET_URL" > /tmp/ab_output.log 2>&1 &
    AB_PID=$!

    # 3. 同时施加系统资源压力 (stress)
    echo -e "${YELLOW}>>> 施加系统资源压力...${NC}" >> $REPORT_FILE
    stress --cpu 2 --vm 1 --vm-bytes 512M --timeout 60s > /dev/null 2>&1 &
    STRESS_PID=$!

    # 4. 监控压力测试期间的资源峰值
    echo -e "${YELLOW}>>> 监控资源使用峰值...${NC}" >> $REPORT_FILE
    for i in {1..10}; do
        echo "[监控快照 $(date +%H:%M:%S)]" >> $REPORT_FILE
        top -bn1 | head -5 | tail -3 >> $REPORT_FILE
        sleep 6
        # 检查ab测试是否结束
        if ! ps -p $AB_PID > /dev/null; then
            break
        fi
    done

    # 等待测试结束
    wait $AB_PID
    kill $STRESS_PID 2>/dev/null

    # 5. 压测后系统状态
    sleep 5  # 等待系统短暂恢复
    echo -e "\n${BLUE}--- 压测后系统状态 ---${NC}" >> $REPORT_FILE
    AFTER_METRICS=$(get_system_metrics "压测后_")

    # 6. 生成AB测试结果摘要
    echo -e "\n${GREEN}=== Web压力测试结果 ===${NC}" >> $REPORT_FILE
    if [ -f /tmp/ab_output.log ]; then
        grep -E "Requests per second:|Time per request:|Failed requests:|Transfer rate:" /tmp/ab_output.log >> $REPORT_FILE
        local failed_requests=$(grep "Failed requests:" /tmp/ab_output.log | awk '{print $3}')
        if [ -z "$failed_requests" ]; then
            failed_requests=0
        fi
        local success_rate=$(safe_calc "100 - $failed_requests * 100 / $TOTAL_REQUESTS")
        echo "请求成功率: ${success_rate}%" >> $REPORT_FILE
    else
        echo "AB测试输出日志未找到，测试可能未正常执行。" >> $REPORT_FILE
    fi

    # 7. 生成对比总结
    echo -e "\n${GREEN}=== 系统负载对比分析 ===${NC}" | tee -a $REPORT_FILE
    echo "==========================================" >> $REPORT_FILE
    echo "指标        | 压测前 | 压测后 | 变化" >> $REPORT_FILE
    echo "------------|--------|--------|------" >> $REPORT_FILE

    # 解析指标
    BEFORE_CPU=$(echo $BEFORE_METRICS | awk '{print $1}')
    BEFORE_MEM=$(echo $BEFORE_METRICS | awk '{print $2}')
    BEFORE_LOAD=$(echo $BEFORE_METRICS | awk '{print $3}')
    BEFORE_CONN=$(echo $BEFORE_METRICS | awk '{print $4}')

    AFTER_CPU=$(echo $AFTER_METRICS | awk '{print $1}')
    AFTER_MEM=$(echo $AFTER_METRICS | awk '{print $2}')
    AFTER_LOAD=$(echo $AFTER_METRICS | awk '{print $3}')
    AFTER_CONN=$(echo $AFTER_METRICS | awk '{print $4}')

    # 计算变化量
    CPU_DIFF=$(safe_calc "$AFTER_CPU - $BEFORE_CPU")
    MEM_DIFF=$(safe_calc "$AFTER_MEM - $BEFORE_MEM")
    LOAD_DIFF=$(safe_calc "$AFTER_LOAD - $BEFORE_LOAD")
    CONN_DIFF=$(safe_calc "$AFTER_CONN - $BEFORE_CONN")

    # 输出对比表格
    {
        echo "CPU使用率 | ${BEFORE_CPU}% | ${AFTER_CPU}% | ${CPU_DIFF}%"
        echo "内存使用率 | ${BEFORE_MEM}% | ${AFTER_MEM}% | ${MEM_DIFF}%"
        echo "系统负载 | ${BEFORE_LOAD} | ${AFTER_LOAD} | ${LOAD_DIFF}"
        echo "HTTP连接数 | ${BEFORE_CONN} | ${AFTER_CONN} | ${CONN_DIFF}"
    } >> $REPORT_FILE

    # 8. 简单性能评估
    echo -e "\n${GREEN}=== 性能评估 ===${NC}" >> $REPORT_FILE
    if [ $(echo "$CPU_DIFF > 10" | bc 2>/dev/null) -eq 1 ]; then
        echo -e "${GREEN}✅ CPU响应明显: 系统正确处理了计算负载。${NC}" >> $REPORT_FILE
    else
        echo -e "${YELLOW}⚠️ CPU响应不明显: 请检查应用配置或测试参数。${NC}" >> $REPORT_FILE
    fi

    if [ $(echo "$LOAD_DIFF > 0.5" | bc 2>/dev/null) -eq 1 ]; then
        echo -e "${GREEN}✅ 系统负载响应明显: 压力测试已产生效果。${NC}" >> $REPORT_FILE
    else
        echo -e "${YELLOW}⚠️ 系统负载变化较小: 可能是并发不足或存在瓶颈。${NC}" >> $REPORT_FILE
    fi

    echo -e "\n${GREEN}=== 测试完成 ===${NC}" | tee -a $REPORT_FILE
    echo -e "详细报告已保存至: $REPORT_FILE\n"
}

# 执行主函数
run_comprehensive_test

import os
import json
import time
import logging
import requests
from dotenv import load_dotenv
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest

# 配置参数 - 根据你的实际环境修改
CONFIG = {
    "aliyun_slb_id": "lb-2zea5bvtsr4a0gtnmutr2",
    "master_ecs_id": "i-2ze7cd5ij7o5qaznr2tk",
    "backup_ecs_id": "i-2ze6iosf5v5rpnzly9ls",
    "aliyun_slb_ip": "39.167.95.191",
    "master_ecs_ip": "172.16.15.4",
    "check_url": "http://172.16.15.4/health.html",
    "retry_times": 3,
    "retry_interval": 2,
    "normal_master_weight": 90,
    "normal_backup_weight": 10,
    "fault_master_weight": 0,
    "fault_backup_weight": 100,
    "log_file": "/root/slb_switch.log",
    "region_id": "cn-beijing"
}

def init_logger():
    """初始化日志配置"""
    # 创建日志目录
    log_dir = os.path.dirname(CONFIG["log_file"])
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    logger = logging.getLogger("slb_switch")
    logger.setLevel(logging.INFO)
    
    file_handler = logging.FileHandler(CONFIG["log_file"])
    file_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    return logger

def init_aliyun_client(logger):
    """初始化阿里云客户端"""
    try:
        load_dotenv("aliyun_env")
        logger.info("成功加载阿里云环境变量文件")
    except Exception as e:
        logger.error(f"加载环境变量文件失败: {str(e)}")
        return None
    
    try:
        access_key_id = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
        access_key_secret = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        
        if not all([access_key_id, access_key_secret]):
            logger.error("环境变量配置不完整")
            return None
            
        client = AcsClient(access_key_id, access_key_secret, CONFIG["region_id"])
        logger.info("阿里云客户端初始化成功")
        return client
    except Exception as e:
        logger.error(f"阿里云客户端初始化失败: {str(e)}")
        return None

def check_master_health(logger):
    """检查主ECS健康状态"""
    # Ping检查
    ping_result = os.system(f"ping -c 2 -w 3 {CONFIG['master_ecs_ip']} > /dev/null 2>&1")
    if ping_result != 0:
        logger.error(f"主ECS {CONFIG['master_ecs_ip']} ping不通")
        return False
    
    # HTTP健康检查
    for i in range(1, CONFIG["retry_times"] + 1):
        try:
            response = requests.get(CONFIG["check_url"], timeout=5)
            if response.status_code == 200:
                logger.info(f"主ECS健康检查通过，第{i}次检查成功")
                return True
            else:
                logger.error(f"主ECS HTTP检查失败，状态码: {response.status_code}")
        except Exception as e:
            logger.error(f"主ECS HTTP检查异常: {str(e)}")
        
        if i < CONFIG["retry_times"]:
            time.sleep(CONFIG["retry_interval"])
    
    logger.error("主ECS健康检查连续失败")
    return False

def get_current_weights(client, logger):
    """获取当前权重"""
    try:
        request = CommonRequest()
        request.set_domain(f"slb.{CONFIG['region_id']}.aliyuncs.com")
        request.set_version("2014-05-15")
        request.set_action_name("DescribeLoadBalancerAttribute")
        request.set_method("GET")
        request.add_query_param("LoadBalancerId", CONFIG["aliyun_slb_id"])
        request.add_query_param("RegionId", CONFIG["region_id"])
        
        response = client.do_action_with_exception(request)
        response_json = json.loads(response.decode("utf-8"))
        
        master_weight = None
        backup_weight = None
        
        backend_servers = response_json.get("BackendServers", {}).get("BackendServer", [])
        for server in backend_servers:
            if server["ServerId"] == CONFIG["master_ecs_id"]:
                master_weight = server["Weight"]
            if server["ServerId"] == CONFIG["backup_ecs_id"]:
                backup_weight = server["Weight"]
        
        if master_weight is None or backup_weight is None:
            logger.error("未找到ECS权重信息")
            return None, None
            
        logger.info(f"当前权重: 主ECS={master_weight}, 备ECS={backup_weight}")
        return master_weight, backup_weight
        
    except Exception as e:
        logger.error(f"获取权重失败: {str(e)}")
        return None, None

def set_weights(client, master_weight, backup_weight, logger):
    """设置权重"""
    try:
        # 先获取当前所有后端服务器
        request = CommonRequest()
        request.set_domain(f"slb.{CONFIG['region_id']}.aliyuncs.com")
        request.set_version("2014-05-15")
        request.set_action_name("DescribeLoadBalancerAttribute")
        request.set_method("GET")
        request.add_query_param("LoadBalancerId", CONFIG["aliyun_slb_id"])
        request.add_query_param("RegionId", CONFIG["region_id"])
        
        response = client.do_action_with_exception(request)
        response_json = json.loads(response.decode("utf-8"))
        backend_servers = response_json.get("BackendServers", {}).get("BackendServer", [])
        
        # 更新权重
        updated_servers = []
        for server in backend_servers:
            server_id = server["ServerId"]
            if server_id == CONFIG["master_ecs_id"]:
                updated_servers.append({"ServerId": server_id, "Weight": str(master_weight)})
            elif server_id == CONFIG["backup_ecs_id"]:
                updated_servers.append({"ServerId": server_id, "Weight": str(backup_weight)})
            else:
                updated_servers.append({"ServerId": server_id, "Weight": str(server["Weight"])})
        
        # 设置权重
        request = CommonRequest()
        request.set_domain(f"slb.{CONFIG['region_id']}.aliyuncs.com")
        request.set_version("2014-05-15")
        request.set_action_name("SetBackendServers")
        request.set_method("POST")
        request.add_query_param("LoadBalancerId", CONFIG["aliyun_slb_id"])
        request.add_query_param("BackendServers", json.dumps(updated_servers))
        
        client.do_action_with_exception(request)
        logger.info(f"权重设置成功: 主ECS={master_weight}, 备ECS={backup_weight}")
        return True
        
    except Exception as e:
        logger.error(f"权重设置失败: {str(e)}")
        return False

def main():
    """主函数"""
    logger = init_logger()
    logger.info("===== SLB自动切换脚本开始执行 =====")
    
    client = init_aliyun_client(logger)
    if client is None:
        logger.error("客户端初始化失败，脚本终止")
        return
    
    # 检查主ECS健康状态
    master_healthy = check_master_health(logger)
    
    # 获取当前权重
    current_master, current_backup = get_current_weights(client, logger)
    if current_master is None or current_backup is None:
        logger.error("获取权重失败，脚本终止")
        return
    
    # 根据健康状态调整权重
    if master_healthy:
        if current_master != CONFIG["normal_master_weight"] or current_backup != CONFIG["normal_backup_weight"]:
            logger.info("主ECS健康，权重异常，开始回切")
            success = set_weights(client, CONFIG["normal_master_weight"], CONFIG["normal_backup_weight"], logger)
            if success:
                logger.info("回切成功")
            else:
                logger.error("回切失败")
        else:
            logger.info("主ECS健康，权重正常，无需操作")
    else:
        if current_master != CONFIG["fault_master_weight"] or current_backup != CONFIG["fault_backup_weight"]:
            logger.info("主ECS异常，开始切换")
            success = set_weights(client, CONFIG["fault_master_weight"], CONFIG["fault_backup_weight"], logger)
            if success:
                logger.info("切换成功")
            else:
                logger.error("切换失败")
        else:
            logger.info("主ECS异常，权重已切换，无需操作")
    
    logger.info("===== SLB自动切换脚本执行结束 =====")

if __name__ == "__main__":
    main()   

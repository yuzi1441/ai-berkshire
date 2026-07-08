; (function (app) {
  app.filter("ljkh", [function ($sce) {  //çº¢å¤´æ ç®è¯¦æ []æ¹ä¸ºãã
    
    return function (originalStr) {
      if(originalStr){
        var tempTxt = originalStr.replace("[","ã");
        return tempTxt.replace("]","ã");
      }
    }
        
  }]);
  var branchArr = ["åäº¬", "å¤©æ´¥", "æ²³å", "å±±è¥¿", "åèå¤", "è¾½å®", "åæ", "é»é¾æ±", "ä¸æµ·", "æ±è", "æµæ±", "å®å¾½", "ç¦å»º", "æ±è¥¿", "å±±ä¸", "æ²³å", "æ¹å", "æ¹å", "å¹¿ä¸", "å¹¿è¥¿", "æµ·å", "éåº", "åå·", "è´µå·", "äºå", "è¥¿è", "éè¥¿", "çè", "éæµ·", "å®å¤", "æ°ç", "å¤§è¿", "å®æ³¢", "å¦é¨", "éå²", "æ·±å³"]
  app.filter("branchFilter", [function ($sce) {  //çº¢å¤´æ ç®è¯¦æ []æ¹ä¸ºãã
    
    return function (originalStr) {
      if(originalStr){
       for(var i=0;i<branchArr.length;i++) {
         if(originalStr === branchArr[i]) {
           return originalStr + 'çç®¡å±'
         }
       }
      }
      return originalStr
    }
        
  }]);
  //   ä¸­å½é¶è¡ä¸çç£ç®¡çå§åä¼(0-12)    ä¸­å½ä¿é©çç£ç®¡çå§åä¼(13-27)   ä¸­å½é¶è¡ä¿é©çç£ç®¡çå§åä¼(28->)    
  var documentNoList = ['ä¸­å½é¶è¡ä¸çç£ç®¡çå§åä¼ä»¤','ä¸­å½é¶çä¼ä»¤','é¶çé','é¶çå½','é¶çå','é¶çå¤','é¶çä¼å¬å','é¶çåå','é¶çåé','é¶çåå½','é¶çåä¾¿å½','èèµæä¿å','èèµæä¿å½','ä¸­å½ä¿é©çç£ç®¡çå§åä¼ä»¤','ä¿çå','ä¿çåå','ä¿çåå½','ä¿çåæ¹','ä¿çç¨½æ¥','ä¿çäººèº«é©','ä¿çå¯¿é©','ä¿çè´¢ä¼','ä¿çäº§é©','ä¿çç»ä¿¡','ä¿çæ¶ä¿','ä¿çä¸­ä»','ä¿çèµé','èµéé¨å½','ä¸­å½é¶è¡ä¿é©çç£ç®¡çå§åä¼ä»¤','é¶ä¿çè§','é¶ä¿çå','é¶ä¿çå¤','é¶ä¿çå½','é¶ä¿çä¼å¬å','é¶ä¿çåå','é¶ä¿çæ¤éè®¸å¯','é¶ä¿çæ³¨éè®¸å¯'];
  var documentNoTitle = '';
  app.filter("documentNoTxt", [function ($sce) {  // çº¢å¤´æ é¢æç§æå·åºå
    
    return function (originalStr,datafrom) {
      if(!originalStr || originalStr === 'å¶ä»' || originalStr === 'æ '){
        return documentNoTitle
      }else {
        tmpTxt = originalStr.split('[')[0];
        for (var i=0;i<documentNoList.length;i++){
          if(tmpTxt == documentNoList[i]){
            return documentNoTitle =  i <=12 ? 'ä¸­å½é¶è¡ä¸çç£ç®¡çå§åä¼' : i <= 27 ? 'ä¸­å½ä¿é©çç£ç®¡çå§åä¼' : 'ä¸­å½é¶è¡ä¿é©çç£ç®¡çå§åä¼'
          }else {
            documentNoTitle = datafrom != null ? '' : 'ä¸­å½é¶è¡ä¿é©çç£ç®¡çå§åä¼';
          }
        }
        return documentNoTitle
      }
    }
        
  }]);
  function isGuiZhang(arr) {
    if (!arr || !(arr instanceof Array)) {
        return 1;
    }
    for (var  i = 0; i < arr.length; i++) {
      // åå¸çæ ç®æ¯å¦åå«è§ç« æ ç® 
      if(arr[i].ItemID == 4214){
        return 2;
      }
    }
    return 1;
  }
  function fixGeneraltype(arr) {
    var itemArr = ['4222','860'];
    for (var  i = 0; i < arr.length; i++) {
      for (var  ii = 0; ii < itemArr.length; ii++) {
        if(arr[i].ItemID == itemArr[ii]){
          return '0';
        }
      }
    }
    return '1';
  }
    app.controller('itemDetailCtrl', function ($scope, global, $rootScope,$timeout) {
        // console.log($rootScope.image_path, 212121)
        // add scope.images
          //å¤æ­æ¯å¦ä¸ºéæåé¡µé¢
        //   $(document).ready(function () {
        //     if (window.location.href.indexOf('static=1') > -1) {
        //         //console.log('static');
        //         $.getScript('/cn/js/common/ngclean.js', function () {
        //             $.ngClean($("body"), { removeAttrs: ["ng-app", "ng-controller", "ng-repeat", "ng-init", "ng-model"], removeClasses: ["ng-binding", "ng-scope"] });
        //             //console.log(staticHtml);
        //             //$(".main").html(staticHtml);
        //         });

        //     }
        // });
       
        // add scope.images
        $scope.isIE8 = false;
        var version = 8.0;  
        var ua = navigator.userAgent.toLowerCase();  
        var isIE = ua.indexOf("msie")>-1;  
        var safariVersion;  
        if(isIE){  
        safariVersion =  ua.match(/msie ([\d.]+)/)[1];  
        }  
        if(safariVersion <= version ){  
          $scope.isIE8 = true;
        }
        var docId = getParam("docId");
        var zfxx_itemId = getParam("itemId");
        var itemType = getParam("type");
        var newbuilddate = "";
        var newpublishDate = "";
        var dadeline = new Date('2019-12-30').getTime();
        var itemId = getParam("itemId");

        $scope.generaltype = getParam("generaltype");
        // if(itemId && fixGeneraltype(itemId)) { //generaltype == 1ä¸éè¦å±ç¤ºçº¢å¤´çå¤ç
        //   $scope.generaltype = '0';
        // }
        if ($scope.generaltype == '1') {
            $scope.showSource = false;//æ¿åºä¿¡æ¯å¬å¼é¡µé¢ä¸­generaltype==1ä¸ºçº¢å¤´çæä»¶ ä¸æ¾ç¤ºæ¥æº
        } else {
            $scope.showSource = true;//æ¿åºä¿¡æ¯å¬å¼é¡µé¢ä¸­generaltype!=1åºæ¬ä¸ä¸æ¯çº¢å¤´ æ¾ç¤ºæ¥æºä½æ­¤æ ç®ä¸çæ³å¾è¡æ¿æ³è§æ ç®é¤å¤ï¼å·ä½å¨é¢åå±ä¸­å¤çäº
        }

        if (docId == undefined || docId == '') {
            return;
        }
        //  æç« ä¸è½½
        $scope.downloadPage = function () {
            if (!window.location.origin) {
                windowURL = window.location.protocol + "//" + window.location.hostname + (window.location.port ? ':' + window.location.port : '');
            } else {
                windowURL = window.location.origin;
            }
            // window.open(windowURL+"/cbircweb/download/downloadPdf?docId=" + docId );
            window.open(windowURL + "/cbircweb/download/downloadPdf?docId=" + docId + "&generaltype=" + $scope.generaltype + "&itemId=" + itemId);


        }
        $scope.docId = docId;
        $scope.rulesDocFileDownload = function (type) {
          // if(itemId==927){
          //     var zcfg=0;
          // }else{
          //     var zcfg=1;
          // }
          var file_urlnew = type ==1? "/cbircweb/download/downloadguizDoc" : "/cbircweb/download/downloadguizPdf";
          // var file_urlnew2=windowURL + "/cbircweb/download/downloadPdf?docId=" + docId+"&zcfg=1";
          $.ajax({
              url: file_urlnew,
              type:"GET",
              data:{docId:docId },
              error: function (xhr, error, ex) {
                  if (xhr.status == '200') {
                      window.location.href = file_urlnew;
                  } else if (xhr.status == '404') {
                      alert("æä»¶ä¸å­å¨ï¼")
                  }else if (xhr.status == '423') {
                      alert("æä»¶å°æªçæï¼")
                  }
              },
              success: function () {
                  window.location.href = file_urlnew+ "?docId=" + docId;
              }
          });
       }
        global.getCDN({ url: '/DocInfo/SelectByDocId', params: { docId: docId } }, function (res) {
            if (res.rptCode == 200 && res.data != null) {
                $scope.isGuiZhang = isGuiZhang(res.data.listTwoItem);
                if(window.location.href.indexOf('governmentDetail') != -1 && fixGeneraltype(res.data.listTwoItem) == '0') {
                    $scope.generaltype = '0';
                    $scope.hideSource = true;
                }
                newbuilddate = new Date(res.data.builddate).getTime();
                newpublishDate = new Date(res.data.publishDate).getTime();
                $scope.data = res.data;
                if(res.data.aviCodeUrl && $scope.isIE8){
                  $("#embed").html('');
                  var vhtml = '<div class="ie-off" style="width:740px;height:416px;background: #000;margin:0 auto;position:relative"><span style="color:#fff">æ¬æµè§å¨ä¸æ¯æè§é¢æ­æ¾ï¼è¯·æ¨éæ©å¶ä»æµè§å¨ã</span></div>'
                  $("#embed").html(vhtml);
                  var videoHtml = '<span style="color:#fff;position:absolute;left:215px">æ¬æµè§å¨ä¸æ¯æè§é¢æ­æ¾ï¼è¯·æ¨éæ©å¶ä»æµè§å¨ã</span><embed src="'+res.data.aviCodeUrl+'" allowScriptAccess="always" width="740" height="416" autostart="false"></embed>'
                  $(".ie-off").html(videoHtml);
                }
                
                //ç¡®è®¤ä¸é¢ä¸æ ä¸çæç« æä¹å±ç¤ºè§é¢ï¼ä¸æå¤åï¼ï¼
                //æ¥åæ¯å¦æè§é¢çå­æ®µå³å¯
                $timeout(function () {
                  var pArr = $('p>span');
                  for(var i=0;i<pArr.length;i++) {
                   if($(pArr[i]).length == 1 && ($(pArr[i])[0].innerHTML == '<br>' || $(pArr[i])[0].innerHTML == '<br />' ||$(pArr[i])[0].innerHTML == '<br/>' ||$(pArr[i])[0].innerHTML == '<BR>' )){
                     $(pArr[i]).addClass('zh-child')
                   }
                  }
                },60);
                // $rootScope.image_path = "images";
                $rootScope.image_path = "images";
                if (global.isRequestSkinJson) {
                    $.ajax({
                        url: '/cn/css/common/data_.json',
                        type: 'get',
                        dataType: 'json',
                        success: function (data) {
                            if (data.data == 'grayscale') {
                                $("body").addClass("grayscale");
                                $rootScope.image_path = "images_gray";
                                $rootScope.isGray = true;
                                $rootScope.svgGrayscaleFilter = "url('#grayscale')";
                                var ieret = global.getIEVersion();
        
                                if (ieret != -1) {
                                    if (ieret >= 10 || ieret == 'edge') {
                                        setTimeout(function(){
                                            if($('#wenzhang-content img').length!=0){
                                                grayscale($('#wenzhang-content img'),function(){
                                                    $rootScope.showSVG = true;
                                                });
                                            }
                                           
                                            setTimeout(function(){
                                                $scope.$apply();
                                            },900)
                                            $scope.$apply();
                                        },1000)
                                    } else {
                                        $rootScope.showSVG = false;
                                    }
                                }
                            } else {
                                $rootScope.image_path = "images";
                                $rootScope.isGray = false;
                                $rootScope.svgGrayscaleFilter = "";
                            }
                        },
                        error: function () {
                            global.getCDN({ url: '/Skin/getCurkind' }, function (res) {
                                if (res.rptCode == 200) {
                                    if (res.data == 'grayscale') {
                                        $("body").addClass("grayscale");
                                      
                                        $rootScope.image_path = "images_gray";
                                        $rootScope.isGray = true;
                                        $rootScope.svgGrayscaleFilter = "url('#grayscale')";
                                        var ieret = global.getIEVersion();
        
                                        if (ieret != -1) {
                                            if (ieret >= 10 || ieret == 'edge') {
                                                // $rootScope.showSVG = true;
                                                // grayscale($('#wenzhang-content'));
                                                setTimeout(function(){
                                                    if($('#wenzhang-content img').length!=0){
                                                        grayscale($('#wenzhang-content img'),function(){
                                                            $rootScope.showSVG = true;
                                                        });
                                                    }
                                                   
                                                    setTimeout(function(){
                                                        $scope.$apply();
                                                    },900)
                                                    $scope.$apply();
                                                },1000)
                                              
                                            } else {
                                                $rootScope.showSVG = false;
                                            }
                                        }
                                    } else {
                                        $rootScope.image_path = "images";
                                        $rootScope.isGray = false;
                                        $rootScope.svgGrayscaleFilter = "";
                                    }
                                } else {
                                    $rootScope.image_path = "images";
                                    $rootScope.isGray = false;
                                    $rootScope.svgGrayscaleFilter = "";
                                }
                            })
                        }
                    })
                } else {
                    global.getCDN({ url: '/Skin/getCurkind' }, function (res) {
                        if (res.rptCode == 200) {
                            if (res.data == 'grayscale') {
                                $("body").addClass("grayscale");
                                $rootScope.image_path = "images_gray";
                                $rootScope.isGray = true;
                                $rootScope.svgGrayscaleFilter = "url('#grayscale')";
                                var ieret = global.getIEVersion();
        
                                if (ieret != -1) {
                                    if (ieret >= 10 || ieret == 'edge') {
                                       setTimeout(function(){
                                            if($('#wenzhang-content img').length!=0){
                                                grayscale($('#wenzhang-content img'),function(){
                                                    $rootScope.showSVG = true;
                                                });
                                            }
                                           
                                            setTimeout(function(){
                                                $scope.$apply();
                                            },900)
                                            $scope.$apply();
                                        },1000)
                                       
                                    } else {
                                        $rootScope.showSVG = false;
                                    }
                                }
                            } else {
                                $rootScope.image_path = "images";
                                $rootScope.isGray = false;
                                $rootScope.svgGrayscaleFilter = "";
                            }
                        } else {
                            $rootScope.image_path = "images";
                            $rootScope.isGray = false;
                            $rootScope.svgGrayscaleFilter = "";
                        }
                    })
                }
                // è®¾ç½®å¤é¾æ¥
                if (res.data.remark2) {
                    $scope.valueArr = res.data.remark2.match(/\[[^\]]+\]\s*[(|ï¼][^)^ï¼^(^ï¼)]+[)|ï¼]\s*/g)// éå½
                    var regExp2 = /\[[^\]]+\]\s*[(|ï¼][^)^ï¼^(^ï¼)]+[)|ï¼]\s*/g;

                    if (regExp2.test(res.data.remark2) == false) {

                        res.data.rules = "1";
                    } else {
                        res.data.rules = "0";

                        $scope.editSubContent = []
                        for (var i = 0; i < $scope.valueArr.length; i++) {
                            $scope.valueArr[i] = $scope.valueArr[i].replace(/(^\s*)|(\s*$)/g);
                            //è§£æå­å¥ç[æ é¢](å°å)

                            $scope.valueArr[i].replace(/\[(.*)\]\s*[\(|ï¼](.*)[\)|ï¼]/, function () {
                                $scope.editSubContent.push({ title: arguments[1], href: arguments[2] })
                                // console.log(arguments)
                            })
                        }

                    }

                } else {

                }
                // è®¾ç½®å¤é¾æ¥
                //    if (res.data.docUuid == "" || res.data.docUuid == null) {
                //     $scope.showTitle = true;
                //   } else if (itemType == "4") {
                //     $scope.showTitle = false;
                //   } else {
                //     $scope.showTitle = false;
                //   }    
                var itemId=getParam('itemId');
                if (res.data.docUuid == "" || res.data.docUuid == null) {
                    // $scope.showTitle = true;
                    // æå·æ¾ç¤º
                        //æ é¢æ¾ç¤ºæåµï¼éå¹´æ¥æåµä¸docUuidä¸ºnullä¸è®ºæå·æå¦åç«¯é½æå¨æ¼ä¸æ é¢
                        $scope.showTitle = true;
                        if ((res.data.documentNo != "" && res.data.documentNo != null) && itemId == 928 ) {
                         //æå·æ¾ç¤ºæåµï¼éå¹´æ¥æåµä¸docUuidä¸ºnullåæ¶æå·ä¸ä¸ºç©ºæ¶æå¨å ä¸æå·
                         if((res.data.documentNo.indexOf("é¶ä¿çä¼ä»¤") == -1)){
                            $scope.showDocNo = true;
                            itemId='';
                         }else{
                            $scope.showDocNo = false;
                         }
                         
                        }else{
                            $scope.showDocNo = false;
                        }
                    // æå·æ¾ç¤º
                } else if (itemType == "4") {
                    $scope.showTitle = false
                } else {
                    $scope.showTitle = false;
                }

                // ä»æ¥å£è·åæçæ¶é´
                var sysBuildDate = '';
                global.getCDN({ url: '/Skin/getSysParams' }, function (re) {
                    if (re.rptCode == 200) {
                        sysBuildDate = re.data.ceremony_time;
                    }
                    // å¦æåææ¥æä¸æ©äºæçæ¶é´ çº¢å¤´å±ç¤ºâå½å®¶éèçç£ç®¡çæ»å±â å¶ä»é»è¾ä¸å
                    if(new Date(res.data.builddate) >= new Date(sysBuildDate)) {
                        $scope.afterCeremony = true;
                        $scope.itemTitle = 'å½å®¶éèçç£ç®¡çæ»å±';
                    } else {
                        $scope.afterCeremony = false;
                        $scope.itemTitle = 'ä¸­å½é¶è¡ä¿é©çç£ç®¡çå§åä¼';
                        // å¤æ­è¥åå¸æ¥æå°äº12æ30ï¼è®©åå¸æ¥æååææ¥æ
                        //  1.åå¸æ¥æå¤§äº12æ30å·ï¼åææ¥æå°äº12æ30å·  å¤çï¼ åææ¥æä»¥åå¸æ¥æä¸ºå
                        //  2.åå¸æ¥æå°äº12æ30å·ï¼åææ¥æå°äº12æ30å·   å¤çï¼åå¸æåææ¥æä¸ºå
                        //  3.åå¸æ¥æå¤§äº12æ30å·ï¼åææ¥æå¤§äº12æ30å·   ä¸å¤çï¼åèªä¸ºåï¼
                        //  4.åå¸æ¥æå°äº12æ30å·ï¼åææ¥æå¤§äº12æ30å·   åå¸æåæ
                        if (res.data.publishDate < '2019-12-30' && newbuilddate != 0 && res.data.builddate < '2019-12-30') {
                            var pubstr = res.data.publishDate.substr(0, 10);
                            res.data.publishDate = res.data.publishDate.replace(pubstr, res.data.builddate);
        
                        }
                        //  console.log('åå¸æ¥æå¤§äº12æ30ãåææ¥æå°äº12æ30å·');
                        //      } 
                        if (res.data.publishDate < '2019-12-30' && newbuilddate != 0 && res.data.builddate > '2019-12-30') {
                            var pubstr2 = res.data.publishDate.substr(0, 10);
                            res.data.publishDate = res.data.publishDate.replace(pubstr2, res.data.builddate);
        
                        }
                        //å¤æ­çº¢å¤´æä»¶é¶ä¿çä¼ãé¶çä¼ãä¿çä¼
                        if (res.data.publishDate >= '2018-03-28' && res.data.datafrom == 0 || res.data.datafrom == null || res.data.datafrom == 2) {
                            $scope.isYinbaojian = true;  //ä¸­å½é¶è¡ä¿é©çç£ç®¡çå§åä¼
                        } else if (res.data.datafrom == 0 && res.data.publishDate < '2018-03-28') {
                            $scope.isYinjian = true;   //ä¸­å½é¶è¡ä¸çç£ç®¡çå§åä¼
                        } else if (res.data.datafrom == 1) {
                            $scope.isBaojian = true;  //ä¸­å½ä¿é©çç£ç®¡çå§åä¼
                        }
        
                    }
                    //wenzhang-contentæ¯å¦å ä¸white-space
                    if (res.data.publishDate < '2019-09-01' || res.data.docUuid != null) {
                        $scope.isWhite_space = false;
                    }
                    else {
                        $scope.isWhite_space = true;
                    }
    
                    $("head > meta[name='ArticleTitle']").attr("content", res.data.docSubtitle);
                    if (res.data.publishDate != undefined) {
    
                        $("head > meta[name='PubDate']").attr("content", res.data.publishDate.substr(0, 16));
                    }
                    $("head > meta[name='ContentSource']").attr("content", res.data.docSource);
                })



                
                //  æç« ç±»åå±ç¤º
                switch (res.data.documentType) {
                    case "0":
                        $scope.documentTypeDetail = "åå";
                        break;
                    case "1":
                        $scope.documentTypeDetail = "è½¬è½½";
                        break;
                    case "2":
                        $scope.documentTypeDetail = "ç¼è¯";
                        break;
                    default:
                        $scope.documentTypeDetail = "æå½";
                        break;
                }
              
                //é¢åå±
                var itemId = getParam("itemId");
                if (res.data.listTwoItem != undefined) {
                    for (var i = 0; i < res.data.listTwoItem.length; i++) {
                        for (var m = 0; m < res.data.listTwoItem[i].ItemLvs.length; m++) {
                            if (res.data.listTwoItem[i].ItemLvs[m] != null) {
                                if (res.data.listTwoItem[i].ItemID == itemId || res.data.listTwoItem[i].ItemLvs[m].itemId == itemId) {
                                    for (j = 0; j < res.data.listTwoItem[i].ItemLvs.length; j++) {
                                        res.data.listTwoItem[i].ItemLvs[j].itemPPid = res.data.listTwoItem[i].ItemLvs[1].itemPid;
                                        res.data.listTwoItem[i].ItemLvs[j].itemsubPId = res.data.listTwoItem[i].ItemLvs[1].itemId;
                                    }
                                    $scope.breadcrumb_detail = res.data.listTwoItem[i].ItemLvs;
                                    //æç« æå±æ ç®åãç§ç±»
                                    $("head > meta[name='ColumnName']").attr("content", $scope.breadcrumb_detail[$scope.breadcrumb_detail.length - 1].itemName);
                                    $("head > meta[name='ColumnType']").attr("content", $scope.breadcrumb_detail[$scope.breadcrumb_detail.length - 1].type);
                                    //å¤æ­æ¯å¦æ¯è¡æ¿è®¸å¯
                                    if ($scope.breadcrumb_detail[$scope.breadcrumb_detail.length - 1].itemName == "æ»å±æºå³") {
                                        $scope.isXingzhengxuke = true;
                                    }
                                    // å¤æ­æ¿åºä¿¡æ¯å¬å¼é¡µé¢ä¸­æ³å¾è¡æ¿æ³è§æ ç®æ°æ®çgeneraltype!=1ï¼æ­¤æ ç®æç« ä¸å¨è¯¦æé¡µæ¾ç¤ºæ¥æº
                                    if ($scope.breadcrumb_detail[$scope.breadcrumb_detail.length - 1].itemName == "æ³å¾è¡æ¿æ³è§") {
                                        $scope.showSource = false;
                                    }

                                    break;
                                }
                            }
                        }
                    }
                }
            }
            $(".content, .footer").show();
        }, function (res) {
            $(".content, .footer").show();

        }, 60 * 1000);
        $.ajax({
            type: 'get',
            url: '../../view/components/sts.html?' + (+ new Date),
            success: function (res) {

            }, 
            error: function (res) {

            }
        });
        //  æç« pdfä¸è½½new
        // $scope.pdfFileDownload = function (docId) {
        //     if (!window.location.origin) {
        //         windowURL = window.location.protocol + "//" + window.location.hostname + (window.location.port ? ':' + window.location.port : '');
        //     } else {
        //         windowURL = window.location.origin;
        //     }
        //     window.open(windowURL + "/cbircweb/download/downloadPdf?docId=" + docId+"&zcfg=1");
        // }
        //  æç« wordä¸è½½new
        // $scope.docFileDownload = function (docId) {
        //     if (!window.location.origin) {
        //         windowURL = window.location.protocol + "//" + window.location.hostname + (window.location.port ? ':' + window.location.port : '');
        //     } else {
        //         windowURL = window.location.origin;
        //     }
        //     window.open(windowURL + "/cbircweb/download/downloadDoc?docId=" + docId);
        // }
        $scope.pdfFileDownload = function (docId) {
            // if (!window.location.origin) {
            //     windowURL = window.location.protocol + "//" + window.location.hostname + (window.location.port ? ':' + window.location.port : '');
            // } else {
            //     windowURL = window.location.origin;
            // }
            // var file_urlnew=windowURL + "/cbircweb/download/downloadPdf?docId=" + docId+"&zcfg=1";
            var file_urlnew = "/cbircweb/download/downloadPdf";
            $.ajax({
                url: file_urlnew,
                type: "GET",
                data: { docId: docId, zcfg: 1 },
                error: function (xhr, error, ex) {
                    if (xhr.status == '200') {
                        window.location.href = file_urlnew;
                    } else if (xhr.status == '404') {
                        alert("æä»¶ä¸å­å¨ï¼")
                    }
                },
                success: function () {
                    window.location.href = file_urlnew + "?docId=" + docId + "&zcfg=1";
                }
            });
        }
        //  æç« wordä¸è½½new
        $scope.docFileDownload = function (docId) {
            // if (!window.location.origin) {
            //     windowURL = window.location.protocol + "//" + window.location.hostname + (window.location.port ? ':' + window.location.port : '');
            // } else {
            //     windowURL = window.location.origin;
            // }
            var file_urlnew = "/cbircweb/download/downloadDoc";
            $.ajax({
                url: file_urlnew,
                type: "GET",
                data: { docId: docId ,zcfg:1,itemId:itemId},
                error: function (xhr, error, ex) {
                    if (xhr.status == '200') {
                        window.location.href = file_urlnew;
                    } else if (xhr.status == '404') {
                        alert("æä»¶ä¸å­å¨ï¼")
                    }else if (xhr.status == '423') {
                        alert("æä»¶å°æªçæï¼")
                    }
                },
                success: function () {
                    window.location.href = file_urlnew + "?docId=" + docId+ "&zcfg=1";
                }
            });
        }

        //å¤æ­urlæ¯å¦æ¯404
        $scope.fileDownload = function (file_url) {
            $.ajax({
                url: file_url,
                error: function (xhr, error, ex) {
                    if (xhr.status == '200') {
                        window.location.href = file_url;
                    } else if (xhr.status == '404') {
                        alert("æä»¶ä¸å­å¨ï¼")
                    }
                },
                success: function () {
                    window.location.href = file_url;
                }
            });
        }
    });

    app.controller('itemDetailRedCtrl', function ($scope, global) {
        $scope.docId = getParam("docId");
        $scope.itemId = getParam("itemId");
    });


    app.controller('rulesDetile', function ($scope, global,$rootScope,$timeout) {
      var docIdd = getParam("docId");
      global.getCDN({ url: '/DocInfo/SelectByDocId', params: { docId: docIdd } }, function (data) {
        if (data.rptCode == 200) {
            $scope.data = data.data
            $scope.docTitle = data.data.docTitle
            $scope.caption = data.data.caption
            $scope.texthtml = data.data.docClob;

            // è§ç« é¡µé¢ metaæ°æ®è¡¥å¨
            $("head > meta[name='ArticleTitle']").attr("content", data.data.docTitle);
            if (data.data.publishDate != undefined) {

                $("head > meta[name='PubDate']").attr("content", data.data.publishDate.substr(0, 16));
            }
            $("head > meta[name='ContentSource']").attr("content", data.data.docSource);
            
            $timeout(function () {
              var pArr = $('p>span');
              for(var i=0;i<pArr.length;i++) {
               if($(pArr[i]).length == 1 && ($(pArr[i])[0].innerHTML == '<br>' || $(pArr[i])[0].innerHTML == '<br />' ||$(pArr[i])[0].innerHTML == '<br/>' ||$(pArr[i])[0].innerHTML == '<BR>')){
                 $(pArr[i]).addClass('zh-child')
               }
              }
            },60);
            if (data.data.remark2) {
              $scope.valueArr = data.data.remark2.match(/\[[^\]]+\]\s*[(|ï¼][^)^ï¼^(^ï¼)]+[)|ï¼]\s*/g)// éå½
              var regExp2 = /\[[^\]]+\]\s*[(|ï¼][^)^ï¼^(^ï¼)]+[)|ï¼]\s*/g;

              if (regExp2.test(data.data.remark2) == false) {

                data.data.rules = "1";
              } else {
                data.data.rules = "0";

                  $scope.editSubContent = []
                  for (var i = 0; i < $scope.valueArr.length; i++) {
                      $scope.valueArr[i] = $scope.valueArr[i].replace(/(^\s*)|(\s*$)/g);
                      //è§£æå­å¥ç[æ é¢](å°å)

                      $scope.valueArr[i].replace(/\[(.*)\]\s*[\(|ï¼](.*)[\)|ï¼]/, function () {
                          $scope.editSubContent.push({ title: arguments[1], href: arguments[2] })
                          // console.log(arguments)
                      })
                  }

              }

          } 
        } else {
            console.log(data);
        }
        
         // ä»æ¥å£è·åæçæ¶é´
         var sysBuildDate = '';
         global.getCDN({ url: '/Skin/getSysParams' }, function (re) {
            if (re.rptCode == 200) {
                sysBuildDate = re.data.ceremony_time;
            }
            // å¦æåææ¥æä¸æ©äºæçæ¶é´ è§ç« çº¢å¤´å±ç¤ºâå½å®¶éèçç£ç®¡çæ»å±è§ç« â å¶ä»é»è¾ä¸å
            if(new Date(data.data.builddate) >= new Date(sysBuildDate)) {
                $scope.rulesTitle = 'å½å®¶éèçç£ç®¡çæ»å±';
            } else {
                $scope.rulesTitle = 'ä¸­å½é¶è¡ä¿é©çç£ç®¡çå§åä¼';
            }
         })

         $(".content, .footer").show();


        }, function (data) {
            console.log(data);
        });
    $scope.itemId = getParam("itemId");
    $scope.rulesDocFileDownload = function (type) {
      // if(itemId==927){
      //     var zcfg=0;
      // }else{
      //     var zcfg=1;
      // }
      var file_urlnew = type ==1? "/cbircweb/download/downloadguizDoc" : "/cbircweb/download/downloadguizPdf";
      // var file_urlnew2=windowURL + "/cbircweb/download/downloadPdf?docId=" + docId+"&zcfg=1";
      $.ajax({
          url: file_urlnew,
          type:"GET",
          data:{docId:docIdd },
          error: function (xhr, error, ex) {
              if (xhr.status == '200') {
                  window.location.href = file_urlnew;
              } else if (xhr.status == '404') {
                  alert("æä»¶ä¸å­å¨ï¼")
              }else if (xhr.status == '423') {
                  alert("æä»¶å°æªçæï¼")
              }
          },
          success: function () {
              window.location.href = file_urlnew+ "?docId=" + docIdd;
          }
      });
  }
  });
})(app);
